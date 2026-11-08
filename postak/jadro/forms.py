from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, SetPasswordForm
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError

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
    first_name = forms.CharField(label='Jméno', max_length=150, required=False)
    role = forms.ChoiceField(label='Role', choices=ROLE)
    password1 = forms.CharField(label='Heslo', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Heslo znovu', widget=forms.PasswordInput)

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('Toto jméno už existuje.')
        return username

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
            first_name=(self.cleaned_data.get('first_name') or '').strip(),
            is_superuser=self.cleaned_data['role'] == 'superuser',
            is_active=True,
        )
        user.set_password(self.cleaned_data['password1'])
        user.save()
        return user
