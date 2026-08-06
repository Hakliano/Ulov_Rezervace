"""Sestavení textů e-mailů pro FLOW preview (před odesláním)."""
from django.template.loader import render_to_string

from rezervace.notifikace_defaults import (
    MANUAL_TYP_NOSHOW,
    MANUAL_TYP_PLATBA,
    MANUAL_TYP_STORNO,
    MANUAL_TYP_ZALOHA,
    MANUAL_TYP_ZALOHA_OK,
    get_manual_notifikace,
)
from rezervace.services.emails import ma_kontaktni_email
from rezervace.services.notifikace_email import render_sablonu
from rezervace.services.zaloha_storno import email_blok_zaloha, zaloha_je_zaplacena


def _to(rezervace):
    return (rezervace.kontaktni_email or '').strip()


def render_storno_draft(rezervace, *, kdo='salon', duvod=''):
    salon = rezervace.salon
    kdo_label = 'salon' if kdo in ('salon', 'admin', 'flow') else 'zákazník'
    predmet = f'Storno rezervace – {salon.name}'
    duvod_txt = (duvod or '').strip() or kdo_label
    zaloha_blok = email_blok_zaloha(rezervace, kdo=kdo_label)
    zaloha_ok = zaloha_je_zaplacena(rezervace)
    zprava = None
    try:
        notif = get_manual_notifikace(salon.rezervacni_nastaveni.notifikace, MANUAL_TYP_STORNO)
        if notif:
            extra = {
                'kdo': kdo_label,
                'duvod': duvod_txt,
                'zaloha_ok': zaloha_ok,
                'zaloha_blok': zaloha_blok,
            }
            predmet = render_sablonu(notif.get('predmet') or predmet, rezervace, extra)
            zprava = render_sablonu(notif.get('text') or '', rezervace, extra)
            if zaloha_blok and 'ZÁLOHA' not in (zprava or ''):
                zprava = (zprava or '').rstrip() + '\n\n' + zaloha_blok
    except Exception:
        zprava = None
    if not zprava:
        zprava = render_to_string('rezervace/emails/storno.txt', {
            'rezervace': rezervace,
            'salon': salon,
            'kdo': kdo_label,
            'duvod': duvod_txt,
            'zaloha_blok': zaloha_blok,
            'zaloha_ok': zaloha_ok,
        })
    return {
        'typ': 'storno',
        'predmet': predmet,
        'text': zprava,
        'to': _to(rezervace),
        'ma_email': ma_kontaktni_email(rezervace),
        'zaloha_zaplacena': zaloha_ok,
    }


def render_manual_draft(rezervace, manual_typ, *, extra_ctx=None, typ_label=None):
    salon = rezervace.salon
    notif = get_manual_notifikace(salon.rezervacni_nastaveni.notifikace, manual_typ)
    if not notif:
        raise ValueError(f'Chybí e-mailová šablona ({manual_typ}).')
    predmet = render_sablonu(notif.get('predmet') or '', rezervace, extra_ctx)
    text = render_sablonu(notif.get('text') or '', rezervace, extra_ctx)
    return {
        'typ': typ_label or manual_typ,
        'predmet': predmet,
        'text': text,
        'to': _to(rezervace),
        'ma_email': ma_kontaktni_email(rezervace),
        'manual_typ': manual_typ,
    }


def render_noshow_draft(rezervace):
    return render_manual_draft(rezervace, MANUAL_TYP_NOSHOW, typ_label='noshow')


def render_zaloha_ok_draft(rezervace):
    extra = {}
    if rezervace.zaloha_castka is not None:
        extra['castka'] = str(rezervace.zaloha_castka)
    return render_manual_draft(
        rezervace, MANUAL_TYP_ZALOHA_OK, extra_ctx=extra, typ_label='zaloha_ok',
    )


def render_platba_draft(rezervace, *, castka, ucet, variabilni_symbol, je_zaloha=False):
    from rezervace.services.platba_qr import generuj_platbu_qr

    salon = rezervace.salon
    typ = MANUAL_TYP_ZALOHA if je_zaloha else MANUAL_TYP_PLATBA
    notif = get_manual_notifikace(salon.rezervacni_nastaveni.notifikace, typ)
    if not notif:
        raise ValueError(
            'Chybí nastavení e-mailu (záloha QR).' if je_zaloha else 'Chybí nastavení e-mailu (platba QR).'
        )
    platba_data = generuj_platbu_qr(ucet, castka, variabilni_symbol, zprava=salon.name)
    extra = {
        'castka': platba_data['castka_display'],
        'ucet': platba_data['ucet'],
        'variabilni_symbol': platba_data['variabilni_symbol'],
    }
    predmet = render_sablonu(notif.get('predmet') or '', rezervace, extra)
    text = render_sablonu(notif.get('text') or '', rezervace, extra)
    return {
        'typ': 'zaloha' if je_zaloha else 'platba',
        'predmet': predmet,
        'text': text,
        'to': _to(rezervace),
        'ma_email': ma_kontaktni_email(rezervace),
        'castka_display': platba_data['castka_display'],
        'ucet': platba_data['ucet'],
        'variabilni_symbol': platba_data['variabilni_symbol'],
        # QR se znovu vygeneruje při odeslání — preview text bez PNG
        'qr_note': 'K e-mailu bude přiložen QR kód pro platbu.',
    }
