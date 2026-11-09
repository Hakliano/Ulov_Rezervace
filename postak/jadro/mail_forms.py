from django import forms
from django.contrib.auth.models import User

from .mail_secrets import encrypt_secret
from .models import EmailSchranka


class SchrankaForm(forms.ModelForm):
    heslo = forms.CharField(
        label='Heslo ke schránce',
        widget=forms.PasswordInput(render_value=False),
        required=False,
        help_text='Při úpravě nechte prázdné, pokud heslo neměníte.',
    )

    class Meta:
        model = EmailSchranka
        fields = [
            'email',
            'projekt',
            'prihlasovaci_jmeno',
            'imap_host',
            'imap_port',
            'imap_ssl',
            'smtp_host',
            'smtp_port',
            'smtp_ssl',
            'smtp_starttls',
        ]
        labels = {
            'prihlasovaci_jmeno': 'Přihlašovací jméno (IMAP/SMTP)',
            'imap_ssl': 'IMAP přes SSL/TLS',
            'smtp_ssl': 'SMTP přes SSL',
            'smtp_starttls': 'SMTP STARTTLS (použít jen bez SSL)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields['heslo'].required = True
            self.fields['heslo'].help_text = ''
        else:
            self.fields['heslo'].label = 'Nové heslo'

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip().lower()
        qs = EmailSchranka.objects.filter(email=email)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('Tato schránka už je v Pošťákovi.')
        return email

    def clean(self):
        data = super().clean()
        if not self.instance.pk and not (data.get('heslo') or '').strip():
            self.add_error('heslo', 'Heslo je povinné.')
        if data.get('smtp_ssl') and data.get('smtp_starttls'):
            self.add_error('smtp_starttls', 'Zvolte buď SSL, nebo STARTTLS.')
        return data

    def save(self, commit=True):
        inst = super().save(commit=False)
        if not (inst.prihlasovaci_jmeno or '').strip():
            inst.prihlasovaci_jmeno = inst.email
        heslo = (self.cleaned_data.get('heslo') or '').strip()
        if heslo:
            inst.heslo_sifra = encrypt_secret(heslo)
        elif not inst.pk:
            inst.heslo_sifra = ''
        if commit:
            inst.save()
            self.save_m2m()
        return inst


class PodpisForm(forms.Form):
    podpis_html = forms.CharField(
        label='HTML podpis',
        widget=forms.Textarea(attrs={'rows': 8}),
        required=False,
        help_text='Vloží se pod odeslané zprávy. Obrázky z URL se v podpisu nezobrazí.',
    )


class SchrankaPristupForm(forms.Form):
    uzivatele = forms.ModelMultipleChoiceField(
        label='Přidělení uživatelé',
        queryset=User.objects.filter(is_active=True).order_by('username'),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
