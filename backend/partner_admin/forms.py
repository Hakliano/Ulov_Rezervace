from decimal import Decimal

from django import forms
from django.utils import timezone

from .models import PartnerNastaveni, PartnerTarif


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
        help_text='1–10 číslic. Nechte prázdné a doplníte později.',
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
    ulov_cislo_uctu = forms.CharField(
        label='Účet ULOV (QR / převod)',
        max_length=34,
        required=False,
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
        self.fields['castka'] = CeskaCastkaField(
            label='Částka (Kč)',
            max_digits=10,
            decimal_places=2,
            min_value=Decimal('0.00'),
            required=False,
            localize=False,
            initial=self.fields['castka'].initial,
            widget=forms.TextInput(attrs={
                'inputmode': 'decimal',
                'autocomplete': 'off',
                'lang': 'en',
            }),
        )


class PartnerNastaveniForm(forms.ModelForm):
    class Meta:
        model = PartnerNastaveni
        fields = [
            'domena',
            'tarif',
            'fakturacni_email',
            'variabilni_symbol',
            'periodicita',
            'castka',
            'dalsi_splatnost',
            'ulov_cislo_uctu',
            'povolit_technicke_nastaveni',
        ]
        widgets = {
            'domena': forms.TextInput(attrs={'autocomplete': 'off', 'spellcheck': 'false'}),
            'fakturacni_email': forms.EmailInput(attrs={'autocomplete': 'off'}),
            'variabilni_symbol': forms.TextInput(attrs={
                'autocomplete': 'off',
                'inputmode': 'numeric',
                'maxlength': '10',
            }),
            'ulov_cislo_uctu': forms.TextInput(attrs={'autocomplete': 'off', 'spellcheck': 'false'}),
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
        self.fields['ulov_cislo_uctu'].required = False
        self.fields['castka'] = CeskaCastkaField(
            label=self.fields['castka'].label,
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
        if (
            not self.is_bound
            and getattr(self.instance, 'castka', None) is not None
        ):
            self.initial['castka'] = f'{self.instance.castka:.2f}'.replace('.', ',')

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
        label='Faktura PDF (volitelné)',
        required=False,
        help_text='PDF se zobrazí majitelce ve FLOW ke stažení.',
    )


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


class BlokaceForm(forms.Form):
    potvrzeni = forms.CharField(label='Pro potvrzení napište BLOCK')
    duvod = forms.CharField(label='Interní důvod', max_length=300, required=False)

    def clean_potvrzeni(self):
        value = self.cleaned_data['potvrzeni'].strip().upper()
        if value != 'BLOCK':
            raise forms.ValidationError('Blokaci potvrďte přesným textem BLOCK.')
        return value
