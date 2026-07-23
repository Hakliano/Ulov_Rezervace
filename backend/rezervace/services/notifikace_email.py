from django.conf import settings
from django.utils import timezone

from rezervace.services.emails import _odeslat_pro_salon, _storno_url, ma_kontaktni_email


def _email_via_celery():
    return bool(getattr(settings, 'EMAIL_VIA_CELERY', False))


def _kontext_rezervace(rezervace):
    salon = rezervace.salon
    sluzby = ', '.join(p.sluzba.nazev for p in rezervace.polozky.all())
    zacatek = timezone_local(rezervace.zacatek)
    recenze_url = ''
    try:
        recenze_url = salon.rezervacni_nastaveni.recenze_url or ''
    except Exception:
        pass
    return {
        'jmeno': rezervace.kontaktni_jmeno,
        'termin': zacatek.strftime('%d.%m.%Y v %H:%M'),
        'termin_datum': zacatek.strftime('%d.%m.%Y'),
        'termin_cas': zacatek.strftime('%H:%M'),
        'sluzby': sluzby,
        'zamestnanec': rezervace.zamestnanec.jmeno if rezervace.zamestnanec else '',
        'adresa': salon.address,
        'telefon': salon.phone,
        'salon': salon,
        'rezervace': rezervace,
        'storno_url': _storno_url(rezervace),
        'recenze_url': recenze_url,
    }


def timezone_local(dt):
    from django.utils import timezone
    if timezone.is_aware(dt):
        return timezone.localtime(dt)
    return dt


def render_sablonu(text, rezervace, extra_ctx=None):
    from django.template import Context, Template, TemplateSyntaxError
    ctx = _kontext_rezervace(rezervace)
    if extra_ctx:
        ctx.update(extra_ctx)
    try:
        return Template(text).render(Context(ctx))
    except TemplateSyntaxError:
        return text


def email_notifikace_sync(rezervace, notifikace, extra_ctx=None):
    if not ma_kontaktni_email(rezervace):
        return False
    salon = rezervace.salon
    predmet = render_sablonu(notifikace['predmet'], rezervace, extra_ctx)
    zprava = render_sablonu(notifikace['text'], rezervace, extra_ctx)
    return _odeslat_pro_salon(salon, rezervace.kontaktni_email, predmet, zprava)


def email_notifikace(rezervace, notifikace, extra_ctx=None):
    if not ma_kontaktni_email(rezervace):
        return False
    if _email_via_celery():
        from rezervace.tasks import task_email_notifikace
        task_email_notifikace.delay(rezervace.pk, notifikace, extra_ctx)
        return True
    return email_notifikace_sync(rezervace, notifikace, extra_ctx=extra_ctx)


def email_platba_qr_sync(rezervace, notifikace, castka, ucet, variabilni_symbol, platba_data=None):
    from rezervace.services.platba_qr import generuj_platbu_qr

    if not ma_kontaktni_email(rezervace):
        return False
    salon = rezervace.salon
    if platba_data is None:
        platba_data = generuj_platbu_qr(ucet, castka, variabilni_symbol, zprava=salon.name)
    qr_png = platba_data['qr_png']
    extra = {
        'castka': platba_data['castka_display'],
        'ucet': platba_data['ucet'],
        'variabilni_symbol': platba_data['variabilni_symbol'],
    }
    predmet = render_sablonu(notifikace['predmet'], rezervace, extra)
    zprava = render_sablonu(notifikace['text'], rezervace, extra)
    html = (
        '<div style="font-family:sans-serif;line-height:1.5">'
        f'<pre style="white-space:pre-wrap;font-family:inherit">{zprava}</pre>'
        '<p><strong>Naskenujte QR kód pro platbu:</strong></p>'
        '<img src="cid:qrplatba" alt="QR platba" style="max-width:220px">'
        '</div>'
    )
    return _odeslat_pro_salon(
        salon,
        rezervace.kontaktni_email,
        predmet,
        zprava,
        html_body=html,
        inline_images=[('qrplatba', qr_png, 'qr_platba.png')],
        attachments=[('qr_platba.png', qr_png, 'image/png')],
    )


def email_platba_qr(rezervace, notifikace, castka, ucet, variabilni_symbol, platba_data=None):
    if not ma_kontaktni_email(rezervace):
        return False
    if _email_via_celery():
        from rezervace.tasks import task_email_platba_qr
        # QR se znovu vygeneruje ve workeru (PNG není vhodné do Redis fronty).
        task_email_platba_qr.delay(
            rezervace.pk, notifikace, castka, ucet, variabilni_symbol
        )
        return True
    return email_platba_qr_sync(
        rezervace, notifikace, castka, ucet, variabilni_symbol, platba_data=platba_data
    )
