from decimal import Decimal

from django import forms
from django.db.models import Q
from django.utils import timezone

from .models import ExtraFaktura, KeyAccountManager, PartnerNastaveni, PartnerTarif, UlovCisloUctu, vychozi_variabilni_symbol


class CeskaCastkaField(forms.DecimalField):
    """Částka z textového pole: 499,00 i 499.00. type=number v CS locale umí odeslat prázdno."""

    def to_python(self, value):
        if isinstance(value, str):
            value = value.strip().replace('\xa0', '').replace(' ', '').replace(',', '.')
        return super().to_python(value)


class TarifSelect(forms.Select):
    def __init__(self, ceny=None, *args, **kwargs):
        self.ceny = ceny or {}
        super().__init__(*args, **kwargs)

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(
            name, value, label, selected, index, subindex=subindex, attrs=attrs,
        )
        if value in self.ceny:
            option['attrs']['data-cena'] = f'{self.ceny[value]:.2f}'.replace('.', ',')
        return option


def nastav_tarif_pole(field, aktualni_nazev=''):
    """Rolovací tarif z katalogu. Cena se u partnera jen předvyplní, jde přepsat."""
    tarify = list(PartnerTarif.objects.filter(aktivni=True).order_by('razeni', 'id'))
    ceny = {row.nazev: row.castka for row in tarify}
    choices = [('', '— vyberte tarif —')] + [(row.nazev, row.nazev) for row in tarify]
    aktualni = (aktualni_nazev or '').strip()
    if aktualni and aktualni not in ceny:
        choices.append((aktualni, f'{aktualni} (mimo katalog)'))
    field.required = False
    field.help_text = 'Po výběru se doplní výchozí cena. Částku můžeš hned přepsat.'
    field.widget = TarifSelect(
        choices=choices,
        ceny=ceny,
        attrs={'autocomplete': 'off', 'class': 'tarif-select'},
    )


def nastav_castku(form, name, label=None, help_text=None, initial=None):
    field = form.fields[name]
    form.fields[name] = CeskaCastkaField(
        label=label or field.label,
        max_digits=getattr(field, 'max_digits', 10),
        decimal_places=2,
        min_value=Decimal('0.00'),
        required=False,
        localize=False,
        initial=initial if initial is not None else getattr(field, 'initial', None),
        help_text=help_text if help_text is not None else field.help_text,
        widget=forms.TextInput(attrs={
            'inputmode': 'decimal',
            'autocomplete': 'off',
            'lang': 'en',
        }),
    )
    instance = getattr(form, 'instance', None)
    if (
        not form.is_bound
        and instance is not None
        and getattr(instance, name, None) is not None
    ):
        hodnota = getattr(instance, name)
        form.initial[name] = f'{hodnota:.2f}'.replace('.', ',')


class PartnerTarifForm(forms.ModelForm):
    class Meta:
        model = PartnerTarif
        fields = ['nazev', 'castka', 'razeni', 'aktivni']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['castka'] = CeskaCastkaField(
            label='Výchozí cena (Kč)',
            max_digits=10,
            decimal_places=2,
            min_value=Decimal('0.00'),
            required=False,
            localize=False,
            widget=forms.TextInput(attrs={
                'inputmode': 'decimal',
                'autocomplete': 'off',
                'lang': 'en',
            }),
        )
        self.fields['razeni'].required = False
        self.fields['aktivni'].required = False
        if not getattr(self.instance, 'pk', None):
            self.fields['aktivni'].initial = True
        if (
            not self.is_bound
            and getattr(self.instance, 'pk', None)
            and self.instance.castka is not None
        ):
            self.initial['castka'] = f'{self.instance.castka:.2f}'.replace('.', ',')

    def clean_nazev(self):
        return (self.cleaned_data.get('nazev') or '').strip()

    def clean_castka(self):
        value = self.cleaned_data.get('castka')
        if value is None:
            return Decimal('0.00')
        return value

    def clean_razeni(self):
        value = self.cleaned_data.get('razeni')
        return 0 if value is None else value


class NovyPartnerForm(forms.Form):
    """Základní založení partnera do DB — bez personálu, fotek a webu."""

    name = forms.CharField(label='Název provozovny', max_length=200)
    address = forms.CharField(label='Adresa', max_length=300, required=False)
    phone = forms.CharField(label='Telefon', max_length=50, required=False)
    email = forms.EmailField(
        label='Kontaktní e-mail (web)',
        required=False,
        help_text='Veřejný kontakt na webu. Může být stejný jako login majitele.',
    )

    majitel_email = forms.EmailField(
        label='E-mail majitele (login web + FLOW)',
        help_text='Unikátní přihlašovací e-mail. Personál a rozvrh doplníte později.',
    )
    majitel_heslo = forms.CharField(
        label='Dočasné heslo majitele',
        min_length=10,
        max_length=128,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        help_text='Min. 10 znaků. Majitel si ho později změní ve web-adminu.',
    )
    aktivovat_flow = forms.BooleanField(
        label='Hned aktivovat FLOW přístup majitele',
        required=False,
        initial=True,
    )
    aktivovat_materialnik = forms.BooleanField(
        label='Hned aktivovat Materiálník (sklad, i bez FLOW)',
        required=False,
        initial=False,
        help_text='Personál se přihlásí stejným e-mailem a heslem. Web ani FLOW k tomu nejsou potřeba.',
    )

    domena = forms.CharField(
        label='Vlastní doména',
        max_length=253,
        required=False,
        help_text='Např. autoservis-novak.cz — bez https://',
    )
    tarif = forms.CharField(
        label='Tarif',
        max_length=100,
        required=False,
    )
    fakturacni_email = forms.EmailField(label='Fakturační e-mail', required=False)
    variabilni_symbol = forms.CharField(
        label='Variabilní symbol',
        max_length=10,
        required=False,
        help_text='Prázdné = 80 a ID partnera (např. 8019). Lze přepsat.',
    )
    periodicita = forms.ChoiceField(
        label='Periodicita',
        choices=PartnerNastaveni.PERIODY,
        initial=PartnerNastaveni.PERIODA_MESIC,
    )
    castka = forms.DecimalField(
        label='Částka (Kč)',
        max_digits=10,
        decimal_places=2,
        initial=Decimal('499.00'),
        min_value=Decimal('0.00'),
        widget=forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
    )
    dalsi_splatnost = forms.DateField(
        label='Další splatnost',
        required=False,
        input_formats=['%Y-%m-%d'],
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
        help_text='Volitelné. Typicky po instalaci / 1. měsíci v poplatku.',
    )
    kam = forms.ModelChoiceField(
        label='KAM',
        queryset=KeyAccountManager.objects.filter(aktivni=True),
        required=False,
        empty_label='— bez KAM —',
    )
    prvni_platba = forms.DecimalField(
        label='První platba (Kč)',
        max_digits=10,
        decimal_places=2,
        required=False,
        initial=Decimal('0.00'),
        min_value=Decimal('0.00'),
        help_text='Co salon zaplatí poprvé (0 / 499 / 2000…). V tom měsíci už nenačítáme tarif.',
    )
    kam_provize = forms.DecimalField(
        label='Provize KAM (Kč)',
        max_digits=10,
        decimal_places=2,
        required=False,
        initial=Decimal('0.00'),
        min_value=Decimal('0.00'),
        help_text='Kolik dostane KAM po zaplacení první platby. 0 = nepočítat.',
    )
    kam_procento = forms.DecimalField(
        label='Provize KAM z dalších plateb (%)',
        max_digits=5,
        decimal_places=2,
        required=False,
        initial=Decimal('0.00'),
        min_value=Decimal('0.00'),
        help_text='Volitelné. Z přijatých plateb po první platbě.',
    )
    ico = forms.CharField(
        label='IČO odběratele',
        max_length=12,
        required=False,
    )
    je_testovaci = forms.BooleanField(
        label='Testovací partner (interní demo, ne zákazník)',
        required=False,
        initial=False,
        help_text='Zařadí provozovnu do Testovacích přístupů. U ostrých partnerů nechte vypnuté.',
    )

    def clean_variabilni_symbol(self):
        vs = (self.cleaned_data.get('variabilni_symbol') or '').strip()
        if not vs:
            return ''
        if not vs.isdigit() or len(vs) > 10:
            raise forms.ValidationError('Variabilní symbol musí obsahovat 1 až 10 číslic.')
        if PartnerNastaveni.objects.filter(variabilni_symbol=vs).exists():
            raise forms.ValidationError('Tento variabilní symbol už používá jiný partner.')
        return vs

    def clean_domena(self):
        domena = (self.cleaned_data.get('domena') or '').strip().lower()
        domena = domena.removeprefix('https://').removeprefix('http://').rstrip('/')
        if '/' in domena:
            raise forms.ValidationError('Zadejte pouze doménu bez cesty.')
        if domena and PartnerNastaveni.objects.filter(domena=domena).exists():
            raise forms.ValidationError('Tato doména už je u jiného partnera.')
        return domena

    def clean_majitel_email(self):
        from rezervace.models import Zamestnanec
        from rezervace.services.staff_auth import normalizuj_prihlasovaci_jmeno
        from flow.models import FlowUser

        email = normalizuj_prihlasovaci_jmeno(self.cleaned_data['majitel_email'])
        if Zamestnanec.objects.filter(
            role=Zamestnanec.ROLE_MAJITEL,
            prihlasovaci_jmeno=email,
        ).exists():
            raise forms.ValidationError('Tento e-mail už má jiný majitel.')
        if FlowUser.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Tento e-mail už používá jiný FLOW účet.')
        return email

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        nastav_tarif_pole(
            self.fields['tarif'],
            (self.data.get('tarif') if self.is_bound else '') or '',
        )
        nastav_castku(self, 'castka', label='Částka (Kč)', initial=self.fields['castka'].initial)
        nastav_castku(self, 'prvni_platba')
        nastav_castku(self, 'kam_provize')
        nastav_castku(self, 'kam_procento')


class PartnerNastaveniForm(forms.ModelForm):
    class Meta:
        model = PartnerNastaveni
        fields = [
            'domena',
            'tarif',
            'kam',
            'prvni_platba',
            'kam_provize',
            'kam_procento',
            'ico',
            'fakturacni_email',
            'variabilni_symbol',
            'periodicita',
            'castka',
            'dalsi_splatnost',
            'povolit_technicke_nastaveni',
            'je_testovaci',
        ]
        widgets = {
            'domena': forms.TextInput(attrs={'autocomplete': 'off', 'spellcheck': 'false'}),
            'fakturacni_email': forms.EmailInput(attrs={'autocomplete': 'off'}),
            'variabilni_symbol': forms.TextInput(attrs={
                'autocomplete': 'off',
                'inputmode': 'numeric',
                'maxlength': '10',
            }),
            # HTML5 type=date vyžaduje ISO YYYY-MM-DD; bez format se v CS locale
            # vykreslí prázdné pole a uložení pak omylem smaže splatnost.
            'dalsi_splatnost': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['dalsi_splatnost'].input_formats = ['%Y-%m-%d', '%d.%m.%Y']
        self.fields['dalsi_splatnost'].required = False
        nastav_tarif_pole(
            self.fields['tarif'],
            (
                (self.data.get(self.add_prefix('tarif')) if self.is_bound else None)
                or getattr(self.instance, 'tarif', '')
                or ''
            ),
        )
        self.fields['fakturacni_email'].required = False
        self.fields['variabilni_symbol'].required = False
        self.fields['variabilni_symbol'].empty_value = None
        self.fields['variabilni_symbol'].help_text = (
            'Výchozí je 80 a ID partnera'
            + (f' ({vychozi_variabilni_symbol(self.instance.salon_id)})' if getattr(self.instance, 'salon_id', None) else '')
            + '. Lze přepsat.'
        )
        self.fields['kam'].required = False
        self.fields['kam'].queryset = KeyAccountManager.objects.filter(aktivni=True)
        if getattr(self.instance, 'kam_id', None):
            self.fields['kam'].queryset = KeyAccountManager.objects.filter(
                Q(aktivni=True) | Q(pk=self.instance.kam_id)
            )
        self.fields['kam'].empty_label = '— bez KAM —'
        self.fields['je_testovaci'].required = False
        self.fields['ico'].required = False
        nastav_castku(self, 'castka')
        nastav_castku(self, 'prvni_platba')
        nastav_castku(self, 'kam_provize')
        nastav_castku(self, 'kam_procento')

    def clean_domena(self):
        domena = (self.cleaned_data.get('domena') or '').strip().lower()
        domena = domena.removeprefix('https://').removeprefix('http://').rstrip('/')
        if '/' in domena:
            raise forms.ValidationError('Zadejte pouze doménu bez cesty.')
        if domena:
            qs = PartnerNastaveni.objects.filter(domena=domena)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError('Tato doména už je u jiného partnera.')
        return domena

    def clean_variabilni_symbol(self):
        vs = (self.cleaned_data.get('variabilni_symbol') or '').strip()
        if not vs:
            vs = vychozi_variabilni_symbol(getattr(self.instance, 'salon_id', None))
        if not vs:
            return None
        if not vs.isdigit() or len(vs) > 10:
            raise forms.ValidationError('Variabilní symbol musí obsahovat 1 až 10 číslic.')
        qs = PartnerNastaveni.objects.filter(variabilni_symbol=vs)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('Tento variabilní symbol už používá jiný partner.')
        return vs

    def clean_castka(self):
        value = self.cleaned_data.get('castka')
        if value is None:
            return Decimal('0.00')
        return value

    def clean_prvni_platba(self):
        return self.cleaned_data.get('prvni_platba') or Decimal('0.00')

    def clean_kam_provize(self):
        return self.cleaned_data.get('kam_provize') or Decimal('0.00')

    def clean_kam_procento(self):
        return self.cleaned_data.get('kam_procento') or Decimal('0.00')

    def clean_ico(self):
        return (self.cleaned_data.get('ico') or '').strip()


class PlatbaForm(forms.Form):
    zaplaceno_dne = forms.DateField(
        label='Datum přijetí platby',
        initial=timezone.localdate,
        input_formats=['%Y-%m-%d'],
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
    )
    prijata_castka = forms.DecimalField(
        label='Přijatá částka',
        max_digits=10,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
    )
    poznamka = forms.CharField(label='Poznámka', max_length=300, required=False)
    faktura_pdf = forms.FileField(
        label='Vlastní PDF faktury (volitelné)',
        required=False,
        help_text='Když nic nenahrajete, faktura UHRAZENO se vygeneruje sama hned po spárování.',
    )


class FakturaEditForm(forms.Form):
    """Šablona faktury k úpravě před vygenerováním PDF."""

    cislo = forms.CharField(label='Číslo faktury', max_length=30)
    datum_vystaveni = forms.CharField(label='Datum vystavení', max_length=20)
    datum_uhrady = forms.CharField(label='Datum úhrady', max_length=20)
    zpusob_uhrady = forms.CharField(label='Způsob úhrady', max_length=40, initial='převodem')
    stav = forms.CharField(label='Stav', max_length=20, initial='UHRAZENO')
    dodavatel_jmeno = forms.CharField(label='Dodavatel — jméno', max_length=120)
    dodavatel_znacka = forms.CharField(label='Dodavatel — značka', max_length=80, required=False)
    dodavatel_ico = forms.CharField(label='Dodavatel — IČO', max_length=12)
    dodavatel_sidlo = forms.CharField(label='Dodavatel — sídlo', max_length=300)
    dodavatel_evidence = forms.CharField(label='Dodavatel — evidence', max_length=80, required=False)
    odberatel_nazev = forms.CharField(label='Odběratel — název', max_length=200)
    odberatel_ico = forms.CharField(label='Odběratel — IČO', max_length=12, required=False)
    odberatel_adresa = forms.CharField(label='Odběratel — adresa', max_length=300, required=False)
    odberatel_email = forms.EmailField(label='Odběratel — e-mail', required=False)
    polozka = forms.CharField(label='Položka', max_length=200)
    obdobi = forms.CharField(label='Období služby', max_length=80)
    castka = CeskaCastkaField(
        label='Částka (Kč)',
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('0.00'),
        localize=False,
        widget=forms.TextInput(attrs={
            'inputmode': 'decimal',
            'autocomplete': 'off',
            'lang': 'en',
        }),
    )
    vs = forms.CharField(label='Variabilní symbol', max_length=10, required=False)
    ucet = forms.CharField(label='Číslo účtu ULOV', max_length=34, required=False)
    poznamka = forms.CharField(label='Poznámka', max_length=300, required=False)

    def data_pro_pdf(self):
        data = dict(self.cleaned_data)
        data['castka'] = f"{data['castka']:.2f}".replace('.', ',')
        data['popis'] = f"{data.get('polozka') or ''} | období {data.get('obdobi') or ''}".strip(' |')
        return data


class FakturaPlatbyForm(forms.Form):
    faktura_pdf = forms.FileField(
        label='Faktura PDF',
        help_text='Nahraje nebo nahradí PDF u vybrané platby.',
    )

    def clean_faktura_pdf(self):
        f = self.cleaned_data['faktura_pdf']
        name = (getattr(f, 'name', '') or '').lower()
        content = getattr(f, 'content_type', '') or ''
        if not (name.endswith('.pdf') or content in ('application/pdf', 'application/x-pdf')):
            raise forms.ValidationError('Nahrajte soubor PDF.')
        if f.size and f.size > 15 * 1024 * 1024:
            raise forms.ValidationError('PDF je příliš velké (max. 15 MB).')
        return f


class UpozorneniForm(forms.Form):
    predmet = forms.CharField(label='Předmět e-mailu', max_length=200)
    text = forms.CharField(
        label='Text e-mailu',
        widget=forms.Textarea(attrs={'rows': 7}),
        max_length=5000,
    )


class HromadnyEmailForm(UpozorneniForm):
    okruh = forms.ChoiceField(
        label='Komu',
        choices=(),
    )
    tarif = forms.ChoiceField(label='Tarif', required=False)

    def __init__(self, *args, tarify=None, **kwargs):
        from .models import HromadnyEmail, PartnerTarif

        super().__init__(*args, **kwargs)
        self.fields['okruh'].choices = HromadnyEmail.OKRUHY
        tarify = tarify if tarify is not None else PartnerTarif.objects.filter(aktivni=True)
        volby = [('', '— vyberte tarif —')] + [(row.nazev, row.nazev) for row in tarify]
        self.fields['tarif'].choices = volby
        self.fields['text'].widget.attrs['rows'] = 10

    def clean(self):
        from .models import HromadnyEmail

        data = super().clean()
        if data.get('okruh') == HromadnyEmail.OKRUH_TARIF and not (data.get('tarif') or '').strip():
            self.add_error('tarif', 'Pro okruh podle tarifu vyberte tarif.')
        return data


class ResetHeslaForm(forms.Form):
    nove_heslo = forms.CharField(
        label='Nové dočasné heslo',
        min_length=10,
        max_length=128,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        help_text='Alespoň 10 znaků. Původní heslo nelze zobrazit.',
    )


class KeyAccountManagerForm(forms.ModelForm):
    class Meta:
        model = KeyAccountManager
        fields = ['jmeno', 'email', 'telefon', 'cislo_uctu', 'razeni', 'aktivni']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].required = False
        self.fields['telefon'].required = False
        self.fields['cislo_uctu'].required = False
        self.fields['razeni'].required = False
        self.fields['aktivni'].required = False
        if not getattr(self.instance, 'pk', None):
            self.fields['aktivni'].initial = True

    def clean_jmeno(self):
        return (self.cleaned_data.get('jmeno') or '').strip()


class UlovCisloUctuForm(forms.ModelForm):
    class Meta:
        model = UlovCisloUctu
        fields = ['cislo', 'popisek', 'primarni', 'razeni', 'aktivni']
        widgets = {
            'cislo': forms.TextInput(attrs={'autocomplete': 'off', 'spellcheck': 'false'}),
            'popisek': forms.TextInput(attrs={'autocomplete': 'off'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['popisek'].required = False
        self.fields['razeni'].required = False
        self.fields['primarni'].required = False
        self.fields['aktivni'].required = False
        if not getattr(self.instance, 'pk', None):
            self.fields['aktivni'].initial = True

    def clean_cislo(self):
        return (self.cleaned_data.get('cislo') or '').strip()


class BlokaceForm(forms.Form):
    potvrzeni = forms.CharField(label='Pro potvrzení napište BLOCK')
    duvod = forms.CharField(label='Interní důvod', max_length=300, required=False)

    def clean_potvrzeni(self):
        value = self.cleaned_data['potvrzeni'].strip().upper()
        if value != 'BLOCK':
            raise forms.ValidationError('Blokaci potvrďte přesným textem BLOCK.')
        return value


class ExtraFakturaForm(forms.Form):
    popis = forms.CharField(
        label='Položka (služba / produkt)',
        max_length=200,
        widget=forms.TextInput(attrs={'placeholder': 'např. NFC stojánek, 4 ks'}),
    )
    castka = CeskaCastkaField(
        label='Částka (Kč)',
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('0.01'),
        localize=False,
        widget=forms.TextInput(attrs={'inputmode': 'decimal', 'autocomplete': 'off', 'lang': 'en'}),
    )
    stav = forms.ChoiceField(label='Stav', choices=ExtraFaktura.STAVY)
    poznamka = forms.CharField(label='Poznámka', max_length=300, required=False)
    odeslat_email = forms.BooleanField(
        label='Odeslat fakturu na fakturační e-mail',
        required=False,
        initial=True,
        help_text='U stavu K úhradě se e-mail odešle vždy.',
    )


class VydajForm(forms.Form):
    datum = forms.DateField(
        label='Datum',
        initial=timezone.localdate,
        input_formats=['%Y-%m-%d'],
        widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
    )
    castka = CeskaCastkaField(
        label='Částka (Kč)',
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('0.01'),
        localize=False,
        widget=forms.TextInput(attrs={'inputmode': 'decimal', 'autocomplete': 'off', 'lang': 'en'}),
    )
    ucet = forms.ModelChoiceField(
        label='Účet',
        queryset=UlovCisloUctu.objects.none(),
        empty_label=None,
    )
    salon = forms.ModelChoiceField(
        label='Partner',
        queryset=None,
        required=False,
        empty_label='Generic — nepatří ke konkrétnímu partnerovi',
    )
    poznamka = forms.CharField(
        label='Poznámka',
        max_length=300,
        widget=forms.TextInput(attrs={'placeholder': 'oběd, vizitky, Hetzner…'}),
    )
    ulozit_sablonu = forms.BooleanField(label='Uložit do šablon', required=False)
    nazev_sablony = forms.CharField(label='Název šablony', max_length=80, required=False)

    def __init__(self, *args, **kwargs):
        from salons.models import Salon

        super().__init__(*args, **kwargs)
        self.fields['ucet'].queryset = UlovCisloUctu.objects.filter(aktivni=True).order_by(
            '-primarni', 'razeni', 'id',
        )
        self.fields['salon'].queryset = Salon.objects.order_by('name')

    def clean(self):
        data = super().clean()
        if data.get('ulozit_sablonu'):
            nazev = (data.get('nazev_sablony') or data.get('poznamka') or '').strip()
            if not nazev:
                self.add_error('nazev_sablony', 'Pro šablonu zadejte název.')
            else:
                data['nazev_sablony'] = nazev[:80]
        return data
