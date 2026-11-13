from django import forms

from phone_scripts.constants import Product


class NewScriptForm(forms.Form):
    name = forms.CharField(max_length=200, label='Název scénáře')
    slug = forms.SlugField(max_length=80, label='Identifikátor (slug)')
    product = forms.ChoiceField(choices=Product.choices, label='Produkt')


class ImportJsonForm(forms.Form):
    MODE_NEW = 'new'
    MODE_VERSION = 'version'
    mode = forms.ChoiceField(
        choices=[
            (MODE_NEW, 'Nový scénář'),
            (MODE_VERSION, 'Nová verze existujícího scénáře'),
        ],
        label='Uložit jako',
        widget=forms.RadioSelect,
    )
    json_file = forms.FileField(label='JSON soubor')
    note = forms.CharField(max_length=500, required=False, label='Poznámka ke změně')
    existing_script = forms.ModelChoiceField(
        queryset=None,
        required=False,
        label='Existující scénář',
    )

    def __init__(self, *args, **kwargs):
        from phone_scripts.models import PhoneScript

        super().__init__(*args, **kwargs)
        self.fields['existing_script'].queryset = PhoneScript.objects.order_by('product', 'name')

    def clean(self):
        data = super().clean()
        if data.get('mode') == self.MODE_VERSION and not data.get('existing_script'):
            self.add_error('existing_script', 'Vyberte scénář pro novou verzi.')
        return data


class PublishConfirmForm(forms.Form):
    confirm = forms.BooleanField(required=True, label='Potvrzuji publikování této verze.')
