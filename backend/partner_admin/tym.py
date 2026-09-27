"""Tým ULOV — zakládání účtů partner-admin. Jen Django superuser."""
from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST

from .forms import TymUzivatelForm
from .models import PartnerAdminProfil
from .permissions import ROLE_ADMIN_FINANCE, ROLE_KAM, partner_admin_perm


def partner_admin_url(request=None):
    """Lokál 127.0.0.1:8000, jinak host z requestu / api.ulovklienty.cz."""
    host = ''
    if request is not None:
        host = (request.get_host() or '').split(':')[0].lower()
        if host in ('127.0.0.1', 'localhost', '::1'):
            return 'http://127.0.0.1:8000/partner-admin/'
        if host:
            schema = 'https' if request.is_secure() else request.scheme
            return f'{schema}://{request.get_host()}/partner-admin/'
    return 'https://api.ulovklienty.cz/partner-admin/'


def _odesli_pristup(jmeno, email, heslo, role, request):
    predmet = 'Přístup do partner-admin ULOV KLIENTY'
    ctx = {
        'jmeno': jmeno,
        'email': email,
        'heslo': heslo,
        'role_label': dict(PartnerAdminProfil.ROLE_CHOICES).get(role, role),
        'panel_url': partner_admin_url(request),
        'login_url': '/partner-admin/login/',
    }
    text = render_to_string('partner_admin/emails/pristup.txt', ctx)
    html = render_to_string('partner_admin/emails/pristup.html', ctx)
    zprava = EmailMultiAlternatives(
        predmet,
        text,
        settings.DEFAULT_FROM_EMAIL,
        [email],
    )
    zprava.attach_alternative(html, 'text/html')
    zprava.send(fail_silently=False)


def vytvor_tym_uzivatele(*, jmeno, email, heslo, role, request=None):
    """Vytvoří staff účet (ne superuser) a zkusí poslat e-mail. Účet zůstane i při chybě mailu."""
    User = get_user_model()
    user = User.objects.create_user(
        username=email,
        email=email,
        password=heslo,
        first_name=jmeno[:150],
        is_staff=True,
        is_superuser=False,
        is_active=True,
    )
    profil = PartnerAdminProfil.objects.create(user=user, jmeno=jmeno, role=role)
    email_ok = True
    email_chyba = ''
    try:
        _odesli_pristup(jmeno, email, heslo, role, request)
    except Exception as exc:
        email_ok = False
        email_chyba = str(exc) or exc.__class__.__name__
    return user, profil, email_ok, email_chyba


@partner_admin_perm('tym')
def seznam(request):
    form = TymUzivatelForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            _user, profil, email_ok, email_chyba = vytvor_tym_uzivatele(
                jmeno=form.cleaned_data['jmeno'],
                email=form.cleaned_data['email'],
                heslo=form.cleaned_data['heslo'],
                role=form.cleaned_data['role'],
                request=request,
            )
            if email_ok:
                messages.success(
                    request,
                    f'Účet pro {profil.jmeno} je vytvořený. Přihlašovací údaje odešly na {profil.user.email}.',
                )
            else:
                messages.warning(
                    request,
                    f'Účet pro {profil.jmeno} je vytvořený, ale e-mail se nepodařilo odeslat'
                    + (f': {email_chyba}' if email_chyba else '.')
                    + ' Přihlašovací údaje předejte ručně.',
                )
            return redirect('partner_admin:tym')
        messages.error(request, 'Účet se nepodařilo založit. Zkontrolujte formulář.')
    clenove = PartnerAdminProfil.objects.select_related('user').order_by('jmeno')
    return render(
        request,
        'partner_admin/tym.html',
        {
            'form': form,
            'clenove': clenove,
            'role_kam': ROLE_KAM,
            'role_finance': ROLE_ADMIN_FINANCE,
        },
    )


@partner_admin_perm('tym')
@require_POST
def smazat(request, pk):
    profil = get_object_or_404(PartnerAdminProfil.objects.select_related('user'), pk=pk)
    user = profil.user
    if user.is_superuser or user.pk == request.user.pk:
        messages.error(request, 'Tohoto uživatele nelze smazat.')
        return redirect('partner_admin:tym')
    jmeno = profil.jmeno
    user.delete()
    messages.success(request, f'Účet „{jmeno}“ je smazaný.')
    return redirect('partner_admin:tym')


__all__ = [
    'partner_admin_url',
    'vytvor_tym_uzivatele',
    'seznam',
    'smazat',
]
