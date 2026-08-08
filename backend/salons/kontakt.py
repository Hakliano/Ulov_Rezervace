"""Veřejný kontaktní formulář partnera — e-mail na salon.email přes SMTP salonu (Forpsi)."""

from rezervace.services.emails import _odeslat_pro_salon, get_email_config

from .models import Salon


def odeslat_kontakt_salonu(salon_id, jmeno, email, telefon, zprava):
    try:
        salon = Salon.objects.get(pk=salon_id)
    except Salon.DoesNotExist as exc:
        raise ValueError('Salon nenalezen.') from exc

    prijemce = (salon.email or '').strip()
    if not prijemce:
        raise ValueError('Salon nemá nastavený kontaktní e-mail.')

    cfg = get_email_config(salon)
    if not cfg.get('smtp_ready'):
        raise ValueError(
            'Odesílání zatím není připravené — v administraci webu doplňte SMTP (Forpsi) a heslo schránky.'
        )

    telefon_txt = (telefon or '').strip() or '—'
    body = (
        f'Nový dotaz z webu {salon.name}\n\n'
        f'Jméno: {jmeno}\n'
        f'E-mail: {email}\n'
        f'Telefon: {telefon_txt}\n\n'
        f'Zpráva:\n{zprava or "—"}\n'
    )
    predmet = f'Dotaz z webu — {salon.name}'
    headers = {'Reply-To': email}

    ok = _odeslat_pro_salon(salon, prijemce, predmet, body, headers=headers)
    if not ok:
        raise ValueError('Odeslání se nepodařilo.')
    return prijemce
