"""Orientační kalkulačka Moderník — výpočet + e-mail, bez ukládání do DB."""

from __future__ import annotations

import math
import re

from django.conf import settings

from rezervace.services.emails import _odeslat_pro_salon
from salons.models import Salon

TYP_PROVOZOVNY = {
    'kaderictvi': 'Kadeřnictví / beauty',
    'veterina': 'Veterinární ordinace',
    'psi_salon': 'Psí salon / grooming',
    'autoservis': 'Autoservis',
    'dental': 'Dentální hygiena',
    'jina': 'Jiná',
}

BASE_PRICE = {6: 3999, 12: 5999}
INCLUDED_EXTRA_PAGES = 4
WEB_BLOCK_SIZE = 3
WEB_BLOCK_MONTHLY = 30
MATERIALNIK_MONTHLY = 99
GROWTH_6M = 999
MAX_PAGES = 1000
MAX_NOTE = 2000
MAX_EMAIL = 254
MAX_PHONE = 40

_EMAIL_RE = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')


class KalkulaceError(ValueError):
    """Neplatná vstupní data kalkulačky."""


def web_monthly(pages: int) -> int:
    extra_pages = max(0, pages - INCLUDED_EXTRA_PAGES)
    if extra_pages == 0:
        return 0
    return math.ceil(extra_pages / WEB_BLOCK_SIZE) * WEB_BLOCK_MONTHLY


def compute_price(pages: int, period_months: int, materialnik: bool, growth: bool) -> dict:
    if period_months not in BASE_PRICE:
        raise KalkulaceError('Zvolte délku partnerství.')
    base = BASE_PRICE[period_months]
    wm = web_monthly(pages)
    mat = MATERIALNIK_MONTHLY if materialnik else 0
    growth_fee = GROWTH_6M if period_months == 6 and growth else 0
    total = base + wm * period_months + mat * period_months + growth_fee
    monthly = round(total / period_months)
    if period_months == 12:
        growth_label = 'ZDARMA'
        period_phrase = 'první rok'
        period_line = '12 měsíců'
    else:
        growth_label = 'ANO +999 Kč' if growth else 'NE'
        period_phrase = 'prvních 6 měsíců'
        period_line = '6 měsíců'
    return {
        'pages': pages,
        'period_months': period_months,
        'materialnik': bool(materialnik),
        'growth': bool(growth) if period_months == 6 else True,
        'web_monthly': wm,
        'materialnik_monthly': mat,
        'growth_fee': growth_fee,
        'total': total,
        'monthly': monthly,
        'growth_label': growth_label,
        'period_phrase': period_phrase,
        'period_line': period_line,
    }


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value or '').strip().lower() in ('1', 'true', 'ano', 'yes', 'on')


def parse_and_compute(data) -> dict:
    if not isinstance(data, dict):
        raise KalkulaceError('Neplatná data.')

    if str(data.get('_gotcha') or '').strip():
        dummy = compute_price(0, 12, False, False)
        dummy['honeypot'] = True
        dummy['email'] = ''
        dummy['telefon'] = ''
        dummy['typ'] = ''
        dummy['typ_label'] = ''
        dummy['poznamka'] = ''
        return dummy

    email = str(data.get('email') or '').strip()
    telefon = str(data.get('telefon') or '').strip()
    typ = str(data.get('typ') or '').strip()
    poznamka = str(data.get('poznamka') or '').strip()

    if not email or len(email) > MAX_EMAIL or not _EMAIL_RE.match(email):
        raise KalkulaceError('Zadejte platný e-mail.')
    if not telefon or len(telefon) > MAX_PHONE:
        raise KalkulaceError('Vyplňte telefon.')
    if typ not in TYP_PROVOZOVNY:
        raise KalkulaceError('Vyberte typ provozovny.')
    if len(poznamka) > MAX_NOTE:
        raise KalkulaceError('Poznámka je příliš dlouhá.')

    try:
        pages = int(data.get('pages'))
    except (TypeError, ValueError):
        raise KalkulaceError('Zadejte počet podstránek jako celé číslo.') from None
    if pages < 0:
        raise KalkulaceError('Počet podstránek nesmí být záporný.')
    if pages > MAX_PAGES:
        raise KalkulaceError('Počet podstránek je mimo rozumný rozsah.')

    try:
        period_months = int(data.get('period'))
    except (TypeError, ValueError):
        raise KalkulaceError('Zvolte délku partnerství.') from None

    materialnik = _as_bool(data.get('materialnik'))
    growth = _as_bool(data.get('growth'))
    result = compute_price(pages, period_months, materialnik, growth)
    result.update({
        'honeypot': False,
        'email': email,
        'telefon': telefon,
        'typ': typ,
        'typ_label': TYP_PROVOZOVNY[typ],
        'poznamka': poznamka,
    })
    return result


def format_email_body(data: dict) -> str:
    note = data['poznamka'] or 'Bez speciálních požadavků.'
    mat_label = 'ANO' if data['materialnik'] else 'NE'
    return (
        'Potenciální zákazník si spočítal Moderníka.\n'
        '\n'
        f'E-mail: {data["email"]}\n'
        f'Telefon: {data["telefon"]}\n'
        '\n'
        f'Typ provozovny: {data["typ_label"]}\n'
        f'Web: hlavní + {data["pages"]} podstránek\n'
        f'Materiálník: {mat_label}\n'
        f'Partnerství: {data["period_line"]}\n'
        f'Program růstu: {data["growth_label"]}\n'
        '\n'
        'Poznámka:\n'
        f'{note}\n'
        '\n'
        'Výsledek:\n'
        f'{data["total"]} Kč / {data["period_phrase"]}\n'
        f'cca {data["monthly"]} Kč / měsíc\n'
    )


def odeslat_kalkulaci(data: dict) -> str:
    try:
        salon = Salon.objects.get(pk=2)
    except Salon.DoesNotExist:
        raise ValueError('Systém není připraven — chybí referenční salon.')

    prijemce = getattr(settings, 'POPTAVKA_EMAIL', '') or salon.email or 'hakl@modernik.cz'
    predmet = f'KALKULÁTOR – nový zájemce – {data["total"]} Kč'
    _odeslat_pro_salon(salon, prijemce, predmet, format_email_body(data))
    return prijemce
