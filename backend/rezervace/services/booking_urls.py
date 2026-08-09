"""Veřejná URL stránky rezervací (odkazy v e-mailech)."""

import re

from django.conf import settings

# Demo / showcase + partneři na LIVE (pk → absolutní rezervace.html)
DEMO_LIVE_BOOKING_URLS = {
    1: 'https://demo1.ulovklienty.cz/rezervace.html',
    2: 'https://demo2.ulovklienty.cz/rezervace.html',
    3: 'https://demo3.ulovklienty.cz/rezervace.html',
    4: 'https://demo4.ulovklienty.cz/rezervace.html',
    5: 'https://demo5.ulovklienty.cz/rezervace.html',
    6: 'https://demo6.ulovklienty.cz/rezervace.html',
    7: 'https://demo7.ulovklienty.cz/rezervace.html',
    8: 'https://demo8.ulovklienty.cz/rezervace.html',
    9: 'https://www.ulovklienty.cz/zdravi-fyzio/rezervace.html',
    10: 'https://www.ulovklienty.cz/zdravi-veterina/rezervace.html',
    11: 'https://www.ulovklienty.cz/zdravi-dental/rezervace.html',
    12: 'https://www.ulovklienty.cz/remesla-instalater/rezervace.html',
    13: 'https://www.ulovklienty.cz/remesla-elektrikar/rezervace.html',
    14: 'https://www.ulovklienty.cz/remesla-rekonstrukce/rezervace.html',
    15: 'https://www.ulovklienty.cz/provoz-autoservis/rezervace.html',
    16: 'https://www.ulovklienty.cz/provoz-pujcovna/rezervace.html',
    17: 'https://www.ulovklienty.cz/provoz-studio/rezervace.html',
    18: 'https://www.franek-autoservis.cloud/rezervace.html',
}


def _je_local_url(url: str) -> bool:
    u = (url or '').strip().lower()
    return (not u) or ('localhost' in u) or u.startswith('http://127.')


def _is_staging() -> bool:
    env = (getattr(settings, 'SENTRY_ENVIRONMENT', '') or '').lower()
    if env == 'staging':
        return True
    api = (getattr(settings, 'API_PUBLIC_BASE_URL', '') or '').lower()
    return 'staging' in api


def _to_staging_booking_url(url: str) -> str:
    """LIVE Ulov hosty → staging (vlastní domény partnerů nechává)."""
    u = (url or '').strip()
    if not u or 'ulovklienty.cz' not in u.lower():
        return u
    u = re.sub(
        r'https://demo(\d)\.ulovklienty\.cz',
        r'https://www.staging.ulovklienty.cz/salon\1',
        u,
        flags=re.IGNORECASE,
    )
    u = re.sub(
        r'https://(?:www\.)?ulovklienty\.cz/',
        'https://www.staging.ulovklienty.cz/',
        u,
        flags=re.IGNORECASE,
    )
    return u


def _dev_localhost_url(salon_id: int) -> str:
    return f'http://localhost:{5499 + int(salon_id)}/rezervace.html'


def _normalize_booking_base(base: str) -> str:
    base = (base or '').strip()
    if not base:
        return ''
    if not base.endswith('.html'):
        base = base.rstrip('/') + '/rezervace.html'
    return base


def resolve_rezervace_web_url(salon) -> str:
    """
    Absolutní URL rezervací pro e-maily.
    Lokálně (DEBUG): DB nebo localhost:{port}.
    Produkce / staging: DB (nesmí být localhost); jinak mapa dem.
    Na stagingu se Ulov LIVE URL přepíšou na staging host.
    """
    try:
        raw = (salon.rezervacni_nastaveni.web_rezervace_url or '').strip()
    except Exception:
        raw = ''

    if settings.DEBUG:
        if raw and not _je_local_url(raw):
            return _normalize_booking_base(raw)
        if raw:
            return _normalize_booking_base(raw)
        return _dev_localhost_url(salon.pk)

    # Produkce / staging bez DEBUG
    if raw and not _je_local_url(raw):
        url = _normalize_booking_base(raw)
        return _to_staging_booking_url(url) if _is_staging() else url

    mapped = DEMO_LIVE_BOOKING_URLS.get(int(salon.pk), '')
    if mapped and _is_staging():
        return _to_staging_booking_url(mapped)
    return mapped
