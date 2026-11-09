"""Odeslání přihlašovacích údajů — systémový e-mail bez ukládání hesla do logů."""

from __future__ import annotations

import logging
import secrets
import string

from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string
from django.utils import timezone

from .mail_send import send_system_message
from .models import EmailSchranka, Profil
from .user_credentials_models import OdeslaniPrihlasovacich

logger = logging.getLogger(__name__)


def prihlasovaci_email_uzivatele(user: User) -> str:
    return (user.email or '').strip() or user.username


def systemova_schranka() -> EmailSchranka | None:
    raw = getattr(settings, 'POSTAK_SYSTEM_SCHRANKA_ID', None)
    if raw not in (None, ''):
        try:
            sid = int(raw)
        except (TypeError, ValueError):
            sid = None
        if sid:
            box = EmailSchranka.objects.filter(pk=sid).first()
            if box:
                return box
    return (
        EmailSchranka.objects.filter(test_stav=EmailSchranka.STAV_OK)
        .order_by('pk')
        .first()
    )


def logo_url_pro_email() -> str:
    """PNG s alfou pro e-mailové klienty (WebP z POSTAK_LOGO_URL v poště často = černé pozadí)."""
    explicit = (getattr(settings, 'POSTAK_EMAIL_LOGO_URL', None) or '').strip()
    if explicit:
        return explicit
    prefix = (getattr(settings, 'POSTAK_PREFIX', '') or '').rstrip('/')
    login = (getattr(settings, 'POSTAK_PUBLIC_LOGIN_URL', '') or '').strip().rstrip('/')
    if login:
        parsed = urlparse(login)
        if parsed.scheme and parsed.netloc:
            return f'{parsed.scheme}://{parsed.netloc}{prefix}/static/postak-logo-email.png'
    return settings.POSTAK_LOGO_URL


def _generuj_heslo(user: User) -> str:
    alphabet = string.ascii_letters + string.digits + '-_'
    for _ in range(12):
        heslo = ''.join(secrets.choice(alphabet) for _ in range(14))
        try:
            validate_password(heslo, user)
            return heslo
        except ValidationError:
            continue
    return secrets.token_urlsafe(12)


def _sablony(user: User, heslo: str, login_url: str) -> tuple[str, str, str]:
    login_id = prihlasovaci_email_uzivatele(user)
    ctx = {
        'uzivatel': user,
        'login_id': login_id,
        'heslo': heslo,
        'login_url': login_url,
        'logo_url': logo_url_pro_email(),
    }
    html = render_to_string('email/prihlasovaci_udaje.html', ctx)
    text = render_to_string('email/prihlasovaci_udaje.txt', ctx)
    subject = f'Přístup do Pošťáka — {login_id}'
    return subject, html, text


def odeslat_prihlasovaci_udaje(*, cil: User, odeslal: User, prijemce: str) -> OdeslaniPrihlasovacich:
    prijemce = (prijemce or '').strip().lower()
    zaznam = OdeslaniPrihlasovacich.objects.create(
        cilovy_uzivatel=cil,
        odeslal=odeslal,
        prijemce=prijemce,
        uspech=False,
    )
    schranka = systemova_schranka()
    if not schranka:
        zaznam.chyba = 'Chybí systémová e-mailová schránka.'
        zaznam.save(update_fields=['chyba'])
        return zaznam
    heslo = _generuj_heslo(cil)
    login_url = settings.POSTAK_PUBLIC_LOGIN_URL
    subject, html, text = _sablony(cil, heslo, login_url)
    try:
        send_system_message(schranka, to=prijemce, subject=subject, html_body=html, text_body=text)
    except Exception as exc:
        zaznam.chyba = str(exc)[:300]
        zaznam.save(update_fields=['chyba'])
        logger.warning(
            'Odeslani prihlasovacich selhalo user=%s prijemce=%s',
            cil.pk,
            prijemce,
        )
        return zaznam
    cil.set_password(heslo)
    cil.save(update_fields=['password'])
    profil, _ = Profil.objects.get_or_create(user=cil)
    profil.vyzadovat_zmenu_hesla = True
    profil.save(update_fields=['vyzadovat_zmenu_hesla'])
    zaznam.uspech = True
    zaznam.chyba = ''
    zaznam.save(update_fields=['uspech', 'chyba'])
    logger.info(
        'Odeslani prihlasovacich ok user=%s prijemce=%s cas=%s',
        cil.pk,
        prijemce,
        timezone.now().isoformat(),
    )
    return zaznam
