from decimal import Decimal

from django import forms
from django.utils import timezone

from .models import PartnerNastaveni


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
        initial='Partner pro vaši provozovnu',
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
            # HTML5 type=date vyžaduje ISO YYYY-MM-DD; bez format se v CS locale
            # vykreslí prázdné pole a uložení pak omylem smaže splatnost.
            'dalsi_splatnost': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'castka': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['dalsi_splatnost'].input_formats = ['%Y-%m-%d']


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
