"""Loga tarifů v partner-adminu — podle názvu vybraného tarifu."""

LOGO_MODERNIK = 'https://haklweb.b-cdn.net/modernik/modernik_logo.webp'
LOGO_MATERIALNIK = 'https://haklweb.b-cdn.net/modernik/materialnik_logo.webp'
LOGO_ARCHIVNIK = 'https://haklweb.b-cdn.net/modernik/logo_archivnik.webp'
LOGO_MODERNIK_ARCHIVNIK = 'https://haklweb.b-cdn.net/modernik/modernik_a_archivnik.webp'
LOGO_MATERIALNIK_ARCHIVNIK = (
    'https://haklweb.b-cdn.net/modernik/Materialn%C3%ADk_a_archivn%C3%ADk.png'
)
LOGO_TROJICE = 'https://haklweb.b-cdn.net/modernik/logo3v1.webp'
LOGO_SPOJENI = 'https://haklweb.b-cdn.net/ULOV_KLIENTA/spojeni3v1.webp'
LOGO_WEB = 'https://haklweb.b-cdn.net/ULOV_KLIENTA/web_pro_salony_logo.webp'
LOGO_OSTATNI = 'https://haklweb.b-cdn.net/ULOV_KLIENTA/New%20Project.webp'

TARIF_LOGA = {
    'moderník': LOGO_MODERNIK,
    'materiálník': LOGO_MATERIALNIK,
    'archivník': LOGO_ARCHIVNIK,
    'moderník + materiálník': LOGO_SPOJENI,
    'moderník + archivník': LOGO_MODERNIK_ARCHIVNIK,
    'materiálník + archivník': LOGO_MATERIALNIK_ARCHIVNIK,
    'moderník + materiálník + archivník': LOGO_TROJICE,
    'web': LOGO_WEB,
}


def _normalizuj_tarif(nazev):
    key = ' '.join((nazev or '').strip().lower().split())
    return key.replace('materialník', 'materiálník')


def logo_url_pro_tarif(nazev):
    key = _normalizuj_tarif(nazev)
    if key in TARIF_LOGA:
        return TARIF_LOGA[key]
    ma_modernik = 'moderník' in key
    ma_materialnik = 'materiálník' in key
    ma_archivnik = 'archivník' in key
    if ma_modernik and ma_materialnik and ma_archivnik:
        return LOGO_TROJICE
    if ma_modernik and ma_archivnik and not ma_materialnik:
        return LOGO_MODERNIK_ARCHIVNIK
    if ma_materialnik and ma_archivnik and not ma_modernik:
        return LOGO_MATERIALNIK_ARCHIVNIK
    if ma_modernik and ma_materialnik:
        return LOGO_SPOJENI
    return LOGO_OSTATNI


def tarif_loga_pro_sablonu():
    return {
        'moderník': LOGO_MODERNIK,
        'materiálník': LOGO_MATERIALNIK,
        'archivník': LOGO_ARCHIVNIK,
        'moderník + archivník': LOGO_MODERNIK_ARCHIVNIK,
        'materiálník + archivník': LOGO_MATERIALNIK_ARCHIVNIK,
        'moderník + materiálník + archivník': LOGO_TROJICE,
        'combo': LOGO_SPOJENI,
        'trojice': LOGO_TROJICE,
        'web': LOGO_WEB,
        'fallback': LOGO_OSTATNI,
    }
