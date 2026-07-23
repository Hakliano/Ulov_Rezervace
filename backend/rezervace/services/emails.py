import os
import secrets
import string

from django.conf import settings
from django.core.mail import EmailMessage, get_connection
from django.template.loader import render_to_string


def generate_heslo(length=12):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def _salon_smtp_env(salon_id, key, fallback=''):
    return os.environ.get(f'SALON_{salon_id}_{key}', fallback)


def get_email_config(salon):
    """SMTP a adresa Od: pro konkrétní salon – primárně z DB (administrace webu)."""
    try:
        nast = salon.rezervacni_nastaveni
    except Exception:
        nast = None

    from_addr = salon.email or (nast.email_odesilatel if nast else '')
    from_name = salon.name or (nast.email_jmeno_odesilatele if nast else '')

    if nast and nast.smtp_user and nast.smtp_password:
        smtp_host = nast.smtp_host or 'smtp.forpsi.com'
        smtp_port = nast.smtp_port or 465
        smtp_user = nast.smtp_user
        smtp_password = nast.smtp_password
        use_ssl = nast.smtp_use_ssl
        use_tls = not use_ssl
        zdroj = 'admin'
    else:
        sid = salon.id
        smtp_host = _salon_smtp_env(sid, 'SMTP_HOST') or settings.EMAIL_HOST
        smtp_port = int(_salon_smtp_env(sid, 'SMTP_PORT') or settings.EMAIL_PORT)
        smtp_user = _salon_smtp_env(sid, 'SMTP_USER') or settings.EMAIL_HOST_USER
        smtp_password = _salon_smtp_env(sid, 'SMTP_PASSWORD') or settings.EMAIL_HOST_PASSWORD
        ssl_env = _salon_smtp_env(sid, 'SMTP_USE_SSL')
        if ssl_env:
            use_ssl = ssl_env.lower() in ('1', 'true', 'yes')
            use_tls = not use_ssl
        elif smtp_port == 465:
            use_ssl = True
            use_tls = False
        else:
            use_ssl = settings.EMAIL_USE_SSL
            use_tls = settings.EMAIL_USE_TLS and not use_ssl
        zdroj = 'env' if smtp_user and smtp_password else 'none'

    if from_name and from_addr:
        from_email = f'{from_name} <{from_addr}>'
    else:
        from_email = from_addr or settings.DEFAULT_FROM_EMAIL

    return {
        'from_email': from_email,
        'from_addr': from_addr,
        'from_name': from_name,
        'host': smtp_host,
        'port': smtp_port,
        'user': smtp_user,
        'password': smtp_password,
        'use_tls': use_tls,
        'use_ssl': use_ssl,
        'smtp_ready': bool(smtp_user and smtp_password),
        'zdroj': zdroj,
    }


def _odeslat_pro_salon(salon, prijemce, predmet, zprava, html_body=None, attachments=None, inline_images=None):
    if not prijemce:
        return False

    # Staging / test: všechny odchozí maily na jednu adresu (nikdy ostrým zákazníkům)
    override = (getattr(settings, 'EMAIL_OVERRIDE_TO', '') or '').strip()
    if override:
        predmet = f"[STAGING → {prijemce}] {predmet}"
        prijemce = override

    cfg = get_email_config(salon)
    # Lokální console backend: vždy vypiš mail do terminálu (i když má salon SMTP v DB).
    use_console = 'console' in (getattr(settings, 'EMAIL_BACKEND', '') or '').lower()
    if use_console or not cfg['smtp_ready']:
        if html_body:
            from django.core.mail import EmailMultiAlternatives

            msg = EmailMultiAlternatives(
                subject=predmet,
                body=zprava,
                from_email=cfg['from_email'],
                to=[prijemce],
            )
            msg.attach_alternative(html_body, 'text/html')
            msg.send()
        else:
            from django.core.mail import send_mail

            send_mail(predmet, zprava, cfg['from_email'], [prijemce], fail_silently=False)
        return True

    connection = get_connection(
        backend='django.core.mail.backends.smtp.EmailBackend',
        host=cfg['host'],
        port=cfg['port'],
        username=cfg['user'],
        password=cfg['password'],
        use_tls=cfg['use_tls'],
        use_ssl=cfg['use_ssl'],
    )

    if html_body and inline_images:
        from email.mime.image import MIMEImage

        from django.core.mail import EmailMultiAlternatives

        msg = EmailMultiAlternatives(
            subject=predmet,
            body=zprava,
            from_email=cfg['from_email'],
            to=[prijemce],
            connection=connection,
        )
        msg.attach_alternative(html_body, 'text/html')
        msg.mixed_subtype = 'related'
        for cid, png_bytes, filename in inline_images:
            img = MIMEImage(png_bytes, _subtype='png')
            img.add_header('Content-ID', f'<{cid}>')
            img.add_header('Content-Disposition', 'inline', filename=filename)
            msg.attach(img)
        for att in attachments or []:
            msg.attach(*att)
        msg.send()
        return True

    if html_body:
        from django.core.mail import EmailMultiAlternatives

        msg = EmailMultiAlternatives(
            subject=predmet,
            body=zprava,
            from_email=cfg['from_email'],
            to=[prijemce],
            connection=connection,
        )
        msg.attach_alternative(html_body, 'text/html')
        for att in attachments or []:
            msg.attach(*att)
        msg.send()
        return True

    msg = EmailMessage(
        subject=predmet,
        body=zprava,
        from_email=cfg['from_email'],
        to=[prijemce],
        connection=connection,
    )
    for att in attachments or []:
        msg.attach(*att)
    msg.send()
    return True


def _salon_dev_port(salon_id):
    """Lokální port statického frontendu: salon 1 → 5500, 2 → 5501, 3 → 5502 …"""
    return 5499 + int(salon_id)


def _storno_url(rezervace):
    try:
        base = (rezervace.salon.rezervacni_nastaveni.web_rezervace_url or '').strip()
    except Exception:
        base = ''
    if not base:
        port = _salon_dev_port(rezervace.salon_id)
        base = f'http://localhost:{port}/rezervace.html'
    elif not base.endswith('.html'):
        base = base.rstrip('/') + '/rezervace.html'
    token = rezervace.cancel_token
    return f'{base}?storno={token}'


def _potvrzeni_url(rezervace):
    try:
        base = (rezervace.salon.rezervacni_nastaveni.web_rezervace_url or '').strip()
    except Exception:
        base = ''
    if not base:
        port = _salon_dev_port(rezervace.salon_id)
        base = f'http://localhost:{port}/rezervace.html'
    elif not base.endswith('.html'):
        base = base.rstrip('/') + '/rezervace.html'
    return f'{base}?potvrdit={rezervace.potvrzeni_token}'


def _rezervace_web_url(salon):
    try:
        url = (salon.rezervacni_nastaveni.web_rezervace_url or '').strip()
    except Exception:
        url = ''
    if not url:
        port = _salon_dev_port(salon.pk)
        return f'http://localhost:{port}/rezervace.html'
    return url


def _email_via_celery():
    return bool(getattr(settings, 'EMAIL_VIA_CELERY', False))


def email_vyzva_k_potvrzeni_sync(rezervace):
    salon = rezervace.salon
    sluzby = ', '.join(p.sluzba.nazev for p in rezervace.polozky.all())
    try:
        platnost = salon.rezervacni_nastaveni.potvrzeni_platnost_hodin or 24
    except Exception:
        platnost = 24
    ctx = {
        'rezervace': rezervace,
        'salon': salon,
        'sluzby': sluzby,
        'potvrzeni_url': _potvrzeni_url(rezervace),
        'platnost_hodin': platnost,
    }
    zprava = render_to_string('rezervace/emails/vyzva_potvrzeni.txt', ctx)
    html = render_to_string('rezervace/emails/vyzva_potvrzeni.html', ctx)
    return _odeslat_pro_salon(
        salon,
        rezervace.kontaktni_email,
        f'Potvrďte rezervaci – {salon.name}',
        zprava,
        html_body=html,
    )


def email_vyzva_k_potvrzeni(rezervace):
    if _email_via_celery():
        from rezervace.tasks import task_email_vyzva_k_potvrzeni
        task_email_vyzva_k_potvrzeni.delay(rezervace.pk)
        return True
    return email_vyzva_k_potvrzeni_sync(rezervace)


def email_potvrzeni_sync(rezervace):
    salon = rezervace.salon
    sluzby = ', '.join(p.sluzba.nazev for p in rezervace.polozky.all())
    storno_url = _storno_url(rezervace)
    rezervace_url = _rezervace_web_url(salon)

    zprava = render_to_string('rezervace/emails/potvrzeni.txt', {
        'rezervace': rezervace,
        'salon': salon,
        'sluzby': sluzby,
        'storno_url': storno_url,
        'rezervace_url': rezervace_url,
    })
    return _odeslat_pro_salon(
        salon,
        rezervace.kontaktni_email,
        f'Potvrzení rezervace – {salon.name}',
        zprava,
    )


def email_potvrzeni(rezervace):
    if _email_via_celery():
        from rezervace.tasks import task_email_potvrzeni
        task_email_potvrzeni.delay(rezervace.pk)
        return True
    return email_potvrzeni_sync(rezervace)


def email_storno_sync(rezervace, kdo='zákazník'):
    salon = rezervace.salon
    zprava = render_to_string('rezervace/emails/storno.txt', {
        'rezervace': rezervace,
        'salon': salon,
        'kdo': kdo,
    })
    _odeslat_pro_salon(salon, rezervace.kontaktni_email, f'Storno rezervace – {salon.name}', zprava)
    if salon.email:
        _odeslat_pro_salon(salon, salon.email, f'Storno rezervace – {rezervace.kontaktni_jmeno}', zprava)


def email_storno(rezervace, kdo='zákazník'):
    if _email_via_celery():
        from rezervace.tasks import task_email_storno
        task_email_storno.delay(rezervace.pk, kdo=kdo)
        return True
    email_storno_sync(rezervace, kdo=kdo)
    return True


def email_nove_heslo_sync(zakaznik, heslo):
    salon = zakaznik.salon
    try:
        base = (salon.rezervacni_nastaveni.web_rezervace_url or '').strip()
    except Exception:
        base = ''
    if not base:
        port = _salon_dev_port(salon.pk)
        base = f'http://localhost:{port}/rezervace.html'
    zprava = render_to_string('rezervace/emails/zapomenute_heslo.txt', {
        'zakaznik': zakaznik,
        'heslo': heslo,
        'salon': salon,
        'rezervace_url': base,
    })
    return _odeslat_pro_salon(salon, zakaznik.email, f'Nové heslo – {salon.name}', zprava)


def email_nove_heslo(zakaznik, heslo):
    if _email_via_celery():
        from rezervace.tasks import task_email_nove_heslo
        task_email_nove_heslo.delay(zakaznik.pk, heslo)
        return True
    return email_nove_heslo_sync(zakaznik, heslo)


def email_test(salon, prijemce):
    """Testovací e-mail vždy synchronně — diagnostika SMTP musí být okamžitá."""
    cfg = get_email_config(salon)
    zprava = (
        f'Toto je testovací e-mail ze salonu {salon.name}.\n\n'
        f'Odesílatel: {cfg["from_email"]}\n'
        f'SMTP server: {cfg["host"]}:{cfg["port"]}\n'
    )
    return _odeslat_pro_salon(salon, prijemce, f'Test e-mail – {salon.name}', zprava)
