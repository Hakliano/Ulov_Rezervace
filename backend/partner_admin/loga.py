"""Loga tarifů v partner-adminu — podle názvu vybraného tarifu."""

LOGO_MODERNIK = 'https://haklweb.b-cdn.net/modernik/modernik_logo.webp'
LOGO_MATERIALNIK = 'https://haklweb.b-cdn.net/modernik/materialnik_logo.webp'
LOGO_SPOJENI = 'https://haklweb.b-cdn.net/ULOV_KLIENTA/spojeni3v1.webp'
LOGO_WEB = 'https://haklweb.b-cdn.net/ULOV_KLIENTA/web_pro_salony_logo.webp'
LOGO_OSTATNI = 'https://haklweb.b-cdn.net/ULOV_KLIENTA/New%20Project.webp'

TARIF_LOGA = {
    'moderník': LOGO_MODERNIK,
    'materiálník': LOGO_MATERIALNIK,
    'web': LOGO_WEB,
}


def _normalizuj_tarif(nazev):
    key = ' '.join((nazev or '').strip().lower().split())
    return key.replace('materialník', 'materiálník')


def logo_url_pro_tarif(nazev):
    key = _normalizuj_tarif(nazev)
    if 'moderník' in key and 'materiálník' in key:
        return LOGO_SPOJENI
    return TARIF_LOGA.get(key, LOGO_OSTATNI)


def tarif_loga_pro_sablonu():
    return {
        'moderník': LOGO_MODERNIK,
        'materiálník': LOGO_MATERIALNIK,
        'combo': LOGO_SPOJENI,
        'web': LOGO_WEB,
        'fallback': LOGO_OSTATNI,
    }
