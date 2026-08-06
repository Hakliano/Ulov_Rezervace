"""Veřejná URL stránky rezervací (odkazy v e-mailech)."""

from django.conf import settings

# Demo / showcase salony na LIVE (pk → absolutní rezervace.html)
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
}


def _je_local_url(url: str) -> bool:
    u = (url or '').strip().lower()
    return (not u) or ('localhost' in u) or u.startswith('http://127.')


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
    Produkce: DB (nesmí být localhost); jinak mapa dem / prázdno.
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
        return _normalize_booking_base(raw)

    mapped = DEMO_LIVE_BOOKING_URLS.get(int(salon.pk))
    if mapped:
        return mapped
    return ''
