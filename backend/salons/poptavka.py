"""Veřejná poptávka z prezentačního webu — odeslání e-mailem přes SMTP salonu 2."""

from django.conf import settings

from rezervace.services.emails import _odeslat_pro_salon
from salons.models import Salon


def odeslat_poptavku(jmeno, email, telefon, salon_nazev, zprava):
    try:
        salon = Salon.objects.get(pk=2)
    except Salon.DoesNotExist:
        raise ValueError('Systém není připraven — chybí referenční salon.')

    prijemce = getattr(settings, 'POPTAVKA_EMAIL', '') or salon.email or 'info@ulovklienty.cz'
    predmet = f'Poptávka Ulov Rezervaci — {salon_nazev or jmeno}'
    telefon_txt = telefon or '—'
    tel_block = f'Telefon: {telefon_txt}\n'
    body = (
        f'Nová poptávka z prezentačního webu Ulov Rezervaci\n\n'
        f'Jméno: {jmeno}\n'
        f'E-mail: {email}\n'
        f'{tel_block}'
        f'Salon / podnik: {salon_nazev or "—"}\n\n'
        f'Zpráva:\n{zprava or "—"}\n'
    )
    _odeslat_pro_salon(salon, prijemce, predmet, body)
    return prijemce
