from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, SetPasswordForm
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError

from .models import Profil
from .obrazky import MAX_FOTO_BYTES, pripona_obrazku, smaz_foto, uloz_foto

ROLE = [('user', 'USER'), ('superuser', 'SUPERUSER')]


class PrihlaseniForm(AuthenticationForm):
    error_messages = {
        'invalid_login': 'Neplatné jméno nebo heslo.',
        'inactive': 'Tento účet je deaktivovaný.',
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = 'Uživatelské jméno'
        self.fields['password'].label = 'Heslo'
        self.fields['username'].widget.attrs['autocomplete'] = 'username'
        self.fields['password'].widget.attrs['autocomplete'] = 'current-password'


class VlastniHesloForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['old_password'].label = 'Současné heslo'
        self.fields['new_password1'].label = 'Nové heslo'
        self.fields['new_password2'].label = 'Nové heslo znovu'


class OdeslatPrihlasovaciForm(forms.Form):
    prijemce = forms.EmailField(label='E-mail příjemce')
    potvrzeni = forms.BooleanField(
        label='Potvrzuji odeslání přístupových údajů na uvedenou adresu',
        required=True,
    )

    def __init__(self, *args, cil_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.cil_user = cil_user
        if cil_user and cil_user.email:
            self.fields['prijemce'].initial = cil_user.email


class HesloUzivateleForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['new_password1'].label = 'Nové heslo'
        self.fields['new_password2'].label = 'Nové heslo znovu'


class NovyUzivatelForm(forms.Form):
    username = forms.CharField(
        label='Uživatelské jméno',
        max_length=150,
        validators=[UnicodeUsernameValidator()],
    )
    email = forms.EmailField(label='E-mail', required=False)
    first_name = forms.CharField(label='Zobrazované jméno', max_length=150, required=False)
    role = forms.ChoiceField(label='Role', choices=ROLE)
    password1 = forms.CharField(label='Heslo', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Heslo znovu', widget=forms.PasswordInput)

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('Toto jméno už existuje.')
        return username

    def clean_email(self):
        return (self.cleaned_data.get('email') or '').strip().lower()

    def clean(self):
        data = super().clean()
        password = data.get('password1')
        if password and data.get('password2') and password != data.get('password2'):
            self.add_error('password2', 'Hesla se neshodují.')
        if password:
            user = User(username=data.get('username') or '')
            try:
                validate_password(password, user)
            except ValidationError as exc:
                self.add_error('password1', exc)
        return data

    def save(self):
        user = User(
            username=self.cleaned_data['username'],
            email=self.cleaned_data.get('email') or '',
            first_name=(self.cleaned_data.get('first_name') or '').strip(),
            is_superuser=self.cleaned_data['role'] == 'superuser',
            is_active=True,
        )
        user.set_password(self.cleaned_data['password1'])
        user.save()
        return user


class UcetForm(forms.Form):
    username = forms.CharField(
        label='Uživatelské jméno',
        max_length=150,
        validators=[UnicodeUsernameValidator()],
    )
    email = forms.EmailField(label='E-mail', required=False)
    first_name = forms.CharField(label='Zobrazované jméno', max_length=150, required=False)
    telefon = forms.CharField(label='Telefon', max_length=40, required=False)

    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        if not args:
            self.fields['username'].initial = user.username
            self.fields['email'].initial = user.email
            self.fields['first_name'].initial = user.first_name
            try:
                self.fields['telefon'].initial = user.profil.telefon
            except Profil.DoesNotExist:
                self.fields['telefon'].initial = ''

    def clean_telefon(self):
        return (self.cleaned_data.get('telefon') or '').strip()[:40]

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        qs = User.objects.exclude(pk=self.user.pk).filter(username=username)
        if qs.exists():
            raise forms.ValidationError('Toto jméno už existuje.')
        return username

    def clean_email(self):
        return (self.cleaned_data.get('email') or '').strip().lower()

    def save(self):
        self.user.username = self.cleaned_data['username']
        self.user.email = self.cleaned_data['email']
        self.user.first_name = (self.cleaned_data.get('first_name') or '').strip()
        self.user.save(update_fields=['username', 'email', 'first_name'])
        profil, _ = Profil.objects.get_or_create(user=self.user)
        profil.telefon = self.cleaned_data.get('telefon') or ''
        profil.save(update_fields=['telefon'])
        return self.user


class ProfilForm(forms.Form):
    email = forms.EmailField(label='E-mail', required=False)
    first_name = forms.CharField(label='Zobrazované jméno', max_length=150, required=False)
    telefon = forms.CharField(label='Telefon', max_length=40, required=False)
    foto = forms.FileField(label='Profilová fotografie', required=False)
    smazat_foto = forms.BooleanField(label='Odstranit fotografii', required=False)

    def __init__(self, *args, user, **kwargs):
        self.user = user
        self._obrazek = None
        super().__init__(*args, **kwargs)
        self.fields['foto'].widget.attrs['accept'] = 'image/jpeg,image/png,image/webp'
        if not args:
            self.fields['email'].initial = user.email
            self.fields['first_name'].initial = user.first_name
            try:
                self.fields['telefon'].initial = user.profil.telefon
            except Profil.DoesNotExist:
                self.fields['telefon'].initial = ''
        if not _ma_foto(user):
            del self.fields['smazat_foto']

    def clean_telefon(self):
        return (self.cleaned_data.get('telefon') or '').strip()[:40]

    def clean_email(self):
        return (self.cleaned_data.get('email') or '').strip().lower()

    def clean_foto(self):
        soubor = self.cleaned_data.get('foto')
        if not soubor:
            return soubor
        if soubor.size > MAX_FOTO_BYTES:
            raise forms.ValidationError('Fotografie může mít nejvýše 2 MB.')
        data = soubor.read(MAX_FOTO_BYTES + 1)
        if len(data) > MAX_FOTO_BYTES:
            raise forms.ValidationError('Fotografie může mít nejvýše 2 MB.')
        pripona = pripona_obrazku(data)
        if not pripona:
            raise forms.ValidationError('Povolené jsou jen JPEG, PNG a WEBP.')
        self._obrazek = (pripona, data)
        return soubor

    def save(self):
        self.user.email = self.cleaned_data['email']
        self.user.first_name = (self.cleaned_data.get('first_name') or '').strip()
        self.user.save(update_fields=['email', 'first_name'])
        profil, _ = Profil.objects.get_or_create(user=self.user)
        profil.telefon = self.cleaned_data.get('telefon') or ''
        profil.save(update_fields=['telefon'])
        if self._obrazek:
            uloz_foto(self.user, *self._obrazek)
        elif self.cleaned_data.get('smazat_foto'):
            smaz_foto(self.user)
        return self.user


def _ma_foto(user):
    try:
        return bool(user.profil.foto)
    except Profil.DoesNotExist:
        return False
