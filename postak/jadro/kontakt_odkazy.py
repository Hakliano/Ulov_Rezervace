"""Bezpečné odkazy web / tel pro výpis kontaktů v Pošťáku."""

from __future__ import annotations

import re
from urllib.parse import urlparse

PHONE_RE = re.compile(r'\D+')
BLOCKED_URL = re.compile(r'^\s*(javascript|data|vbscript|file|blob):', re.IGNORECASE)
POVOLENE_SCHEMATA = frozenset({'http', 'https'})


def normalizuj_telefon_cisla(raw: str) -> str:
    digits = PHONE_RE.sub('', raw or '')
    if not digits:
        return ''
    if digits.startswith('00420') and len(digits) > 12:
        digits = digits[5:]
    elif digits.startswith('420') and len(digits) > 9:
        digits = digits[3:]
    if len(digits) >= 9:
        digits = digits[-9:]
    else:
        return ''
    if len(set(digits)) == 1:
        return ''
    return digits


def web_odkaz(raw: str) -> dict | None:
    zdroj = (raw or '').strip()
    if not zdroj:
        return None
    if BLOCKED_URL.match(zdroj):
        return None
    href = zdroj
    if '://' not in href:
        href = 'https://' + href.lstrip('/')
    parsed = urlparse(href)
    scheme = (parsed.scheme or '').lower()
    if scheme not in POVOLENE_SCHEMATA or not parsed.netloc:
        return None
    label = zdroj if len(zdroj) <= 48 else zdroj[:45] + '…'
    return {'href': href, 'label': label}


def telefon_odkaz(raw: str) -> dict | None:
    zobrazeni = (raw or '').strip()
    if not zobrazeni:
        return None
    digits = normalizuj_telefon_cisla(raw)
    if not digits:
        return None
    href = f'tel:+420{digits}' if len(digits) == 9 else f'tel:+{digits}'
    return {'href': href, 'label': zobrazeni}