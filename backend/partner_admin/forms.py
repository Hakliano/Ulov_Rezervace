from django import forms
from django.utils import timezone

from .models import PartnerNastaveni


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
