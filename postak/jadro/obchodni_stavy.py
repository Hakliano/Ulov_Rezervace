"""Společný číselník obchodních stavů (shodný s Moderník/HYA)."""

OBCHODNI_STAVY = [
    ('lead_pred_webu', 'Lead před kontrolou webu'),
    ('lead_po_webu', 'Lead po kontrole webu'),
    ('kontakt_email', 'Kontaktován e-mailem'),
    ('kontakt_sms', 'Kontaktován SMS'),
    ('kontakt_telefon', 'Kontaktován telefonicky'),
    ('kontakt_osobne', 'Kontaktován osobně'),
    ('nefunkcni_telefon', 'Nefunkční telefon'),
    ('zavolat_znovu', 'Zavolat znovu'),
    ('ozvat_se_pozdeji', 'Ozvat se později'),
    ('domluvena_schuzka', 'Domluvená schůzka'),
    ('nema_zajem', 'Nemá zájem'),
    ('ma_zajem', 'Má zájem'),
    ('prodano', 'Prodáno'),
    ('nechceme', 'Nechceme'),
]

OBCHODNI_STAV_KODY = {k for k, _ in OBCHODNI_STAVY}
OBCHODNI_STAV_LABELS = dict(OBCHODNI_STAVY)

# Historické kódy HYA (před sjednocením) → kanonický kód.
CANON_TO_HYA_API = {canon: legacy for legacy, canon in {
    'lead_before_web': 'lead_pred_webu',
    'lead_after_web': 'lead_po_webu',
    'contacted_email': 'kontakt_email',
    'contacted_sms': 'kontakt_sms',
    'contacted_phone': 'kontakt_telefon',
    'contacted_person': 'kontakt_osobne',
    'bad_phone': 'nefunkcni_telefon',
    'call_again': 'zavolat_znovu',
    'contact_later': 'ozvat_se_pozdeji',
    'meeting_set': 'domluvena_schuzka',
    'not_interested': 'nema_zajem',
    'interested': 'ma_zajem',
    'sold': 'prodano',
    'unwanted': 'nechceme',
}.items()}

HYA_LEGACY_STATUS_MAP = {
    'lead_before_web': 'lead_pred_webu',
    'lead_after_web': 'lead_po_webu',
    'contacted_email': 'kontakt_email',
    'contacted_sms': 'kontakt_sms',
    'contacted_phone': 'kontakt_telefon',
    'contacted_person': 'kontakt_osobne',
    'bad_phone': 'nefunkcni_telefon',
    'call_again': 'zavolat_znovu',
    'contact_later': 'ozvat_se_pozdeji',
    'meeting_set': 'domluvena_schuzka',
    'not_interested': 'nema_zajem',
    'interested': 'ma_zajem',
    'sold': 'prodano',
    'unwanted': 'nechceme',
}


def kanon_z_api_stavu(kod: str) -> str:
    k = (kod or '').strip()
    if k in OBCHODNI_STAV_KODY:
        return k
    return HYA_LEGACY_STATUS_MAP.get(k, k)


def kanon_do_hya_api(kod: str) -> str:
    k = kanon_z_api_stavu(kod)
    return CANON_TO_HYA_API.get(k, k)


def kanon_do_modernik(kod: str) -> str:
    return kanon_z_api_stavu(kod)


def stavy_spolecne_pro_ui():
    return [{'kod': k, 'label': l} for k, l in OBCHODNI_STAVY]