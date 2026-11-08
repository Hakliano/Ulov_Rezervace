"""Tým ULOV — zakládání účtů partner-admin. Jen Django superuser."""
from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST

from .forms import TymUpravaForm, TymUzivatelForm
from .models import PartnerAdminProfil
from .permissions import (
    ROLE_ADMIN_FINANCE,
    ROLE_KAM,
    partner_admin_perm,
    partner_admin_profil,
)
from .services import vygeneruj_demo_heslo


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


def _odesli_pristup(jmeno, email, heslo, role, request, *, znovu=False):
    predmet = (
        'Nové heslo do partner-admin ULOV KLIENTY'
        if znovu
        else 'Přístup do partner-admin ULOV KLIENTY'
    )
    ctx = {
        'jmeno': jmeno,
        'email': email,
        'heslo': heslo,
        'role_label': dict(PartnerAdminProfil.ROLE_CHOICES).get(role, role),
        'panel_url': partner_admin_url(request),
        'login_url': '/partner-admin/login/',
        'znovu': znovu,
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


def _chyba_upravy_tymu(request, user):
    if user.is_superuser:
        return 'Superadmin se spravuje mimo Tým ULOV.'
    if user.pk == request.user.pk:
        return 'Vlastní účet tady neupravujte.'
    if partner_admin_profil(user) is None:
        return 'Toto není týmový účet partner-admin.'
    return ''


def _uprava_form_z_request(request):
    raw = (request.GET.get('upravit') or '').strip()
    if not raw.isdigit():
        return None, None
    profil = PartnerAdminProfil.objects.select_related('user').filter(pk=int(raw)).first()
    if not profil or _chyba_upravy_tymu(request, profil.user):
        return None, None
    initial = {
        'jmeno': profil.jmeno,
        'email': profil.user.email,
        'role': profil.role,
    }
    return profil, TymUpravaForm(initial=initial, profil=profil)


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
    edituje, uprava_form = _uprava_form_z_request(request)
    return render(
        request,
        'partner_admin/tym.html',
        {
            'form': form,
            'clenove': clenove,
            'role_kam': ROLE_KAM,
            'role_finance': ROLE_ADMIN_FINANCE,
            'edituje': edituje,
            'uprava_form': uprava_form,
        },
    )


@partner_admin_perm('tym')
@require_POST
def ulozit(request, pk):
    profil = get_object_or_404(PartnerAdminProfil.objects.select_related('user'), pk=pk)
    user = profil.user
    chyba = _chyba_upravy_tymu(request, user)
    if chyba:
        messages.error(request, chyba)
        return redirect('partner_admin:tym')
    form = TymUpravaForm(request.POST, profil=profil)
    if not form.is_valid():
        messages.error(request, 'Údaje se nepodařilo uložit. Zkontrolujte formulář.')
        return redirect(f'{reverse("partner_admin:tym")}?upravit={pk}')
    jmeno = form.cleaned_data['jmeno']
    email = form.cleaned_data['email']
    role = form.cleaned_data['role']
    email_zmenen = (user.email or '').lower() != email or user.username.lower() != email
    with transaction.atomic():
        profil.jmeno = jmeno
        profil.role = role
        profil.save(update_fields=['jmeno', 'role'])
        user.email = email
        user.username = email
        user.first_name = jmeno[:150]
        user.save(update_fields=['email', 'username', 'first_name'])
    if email_zmenen:
        messages.success(
            request,
            f'Účet {jmeno} je uložený. Přihlášení je teď {email} — pošlete přístup znovu, '
            'pokud má dostat heslo.',
        )
    else:
        messages.success(request, f'Účet {jmeno} je uložený.')
    return redirect('partner_admin:tym')


@partner_admin_perm('tym')
@require_POST
def smazat(request, pk):
    profil = get_object_or_404(PartnerAdminProfil.objects.select_related('user'), pk=pk)
    user = profil.user
    if _chyba_upravy_tymu(request, user):
        messages.error(request, 'Tohoto uživatele nelze smazat.')
        return redirect('partner_admin:tym')
    jmeno = profil.jmeno
    user.delete()
    messages.success(request, f'Účet „{jmeno}“ je smazaný.')
    return redirect('partner_admin:tym')


@partner_admin_perm('tym')
@require_POST
def poslat_pristup_znovu(request, pk):
    profil = get_object_or_404(PartnerAdminProfil.objects.select_related('user'), pk=pk)
    user = profil.user
    chyba = _chyba_upravy_tymu(request, user)
    if chyba:
        messages.error(request, chyba)
        return redirect('partner_admin:tym')
    if not user.is_active:
        messages.error(
            request,
            f'Účet {profil.jmeno} je zablokovaný. Nejdřív ho aktivujte, pak pošlete přístup.',
        )
        return redirect('partner_admin:tym')
    heslo = vygeneruj_demo_heslo(14)
    user.set_password(heslo)
    user.save(update_fields=['password'])
    try:
        _odesli_pristup(profil.jmeno, user.email, heslo, profil.role, request, znovu=True)
    except Exception as exc:
        ch = str(exc) or exc.__class__.__name__
        messages.warning(
            request,
            f'Heslo pro {profil.jmeno} je nové, ale e-mail se nepodařilo odeslat'
            + (f': {ch}' if ch else '.')
            + ' Předejte heslo ručně.',
        )
        return redirect('partner_admin:tym')
    messages.success(
        request,
        f'Nové heslo pro {profil.jmeno} odešlo na {user.email}. Staré heslo už neplatí.',
    )
    return redirect('partner_admin:tym')


@partner_admin_perm('tym')
@require_POST
def zablokovat(request, pk):
    profil = get_object_or_404(PartnerAdminProfil.objects.select_related('user'), pk=pk)
    user = profil.user
    chyba = _chyba_upravy_tymu(request, user)
    if chyba:
        messages.error(request, chyba)
        return redirect('partner_admin:tym')
    if not user.is_active:
        messages.info(request, f'Účet {profil.jmeno} už je zablokovaný.')
        return redirect('partner_admin:tym')
    user.is_active = False
    user.save(update_fields=['is_active'])
    messages.success(
        request,
        f'Přístup pro {profil.jmeno} je zablokovaný. Do panelu se nepřihlásí.',
    )
    return redirect('partner_admin:tym')


@partner_admin_perm('tym')
@require_POST
def aktivovat(request, pk):
    profil = get_object_or_404(PartnerAdminProfil.objects.select_related('user'), pk=pk)
    user = profil.user
    chyba = _chyba_upravy_tymu(request, user)
    if chyba:
        messages.error(request, chyba)
        return redirect('partner_admin:tym')
    if user.is_active:
        messages.info(request, f'Účet {profil.jmeno} už je aktivní.')
        return redirect('partner_admin:tym')
    user.is_active = True
    user.save(update_fields=['is_active'])
    messages.success(request, f'Přístup pro {profil.jmeno} je aktivní. Pošlete přihlašovací údaje, pokud je potřebuje.')
    return redirect('partner_admin:tym')


__all__ = [
    'partner_admin_url',
    'vytvor_tym_uzivatele',
    'seznam',
    'smazat',
    'poslat_pristup_znovu',
    'zablokovat',
    'aktivovat',
    'ulozit',
]
