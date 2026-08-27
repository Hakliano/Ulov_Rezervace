"""URL testovacích dem — lokál i staging, podle ID salonu."""

from django.conf import settings

from rezervace.models import Zamestnanec
from rezervace.services.booking_urls import (
    DEMO_LIVE_BOOKING_URLS,
    _dev_localhost_url,
    _to_staging_booking_url,
)

from .models import MODUL_MATERIALNIK, PartnerModul
from .services_moduly import partner_modul

DEMO_CESTY = {
    1: 'salon1',
    2: 'salon2',
    3: 'salon3',
    4: 'salon4',
    5: 'salon5',
    6: 'salon6',
    7: 'salon7',
    8: 'salon8',
    9: 'zdravi-fyzio',
    10: 'zdravi-veterina',
    11: 'zdravi-dental',
    12: 'remesla-instalater',
    13: 'remesla-elektrikar',
    14: 'remesla-rekonstrukce',
    15: 'provoz-autoservis',
    16: 'provoz-pujcovna',
    17: 'provoz-studio',
    18: 'provoz-franek',
    19: 'salon19',
}

FLOW_LOCAL = 'http://localhost:8080/flow/'
FLOW_STAGING = 'https://www.staging.ulovklienty.cz/flow/'
SKLAD_LOCAL = 'http://127.0.0.1:8001/'
SKLAD_STAGING = 'https://www.staging.ulovklienty.cz/sklad/'


def _domu_z_rezervace(url):
    u = (url or '').strip()
    if u.endswith('rezervace.html'):
        return u[: -len('rezervace.html')]
    return u.rstrip('/') + '/' if u else ''


def _web_staging(salon):
    slug = DEMO_CESTY.get(int(salon.pk))
    if slug:
        return f'https://www.staging.ulovklienty.cz/{slug}/'
    mapped = DEMO_LIVE_BOOKING_URLS.get(int(salon.pk), '')
    if mapped:
        return _domu_z_rezervace(_to_staging_booking_url(mapped))
    domena = (getattr(getattr(salon, 'partner_nastaveni', None), 'domena', '') or '').strip()
    if domena:
        return f'https://{domena}/'
    return ''


def _web_local(salon):
    slug = DEMO_CESTY.get(int(salon.pk))
    port = 5499 + int(salon.pk)
    if slug:
        return f'http://localhost:{port}/'
    return f'http://localhost:{port}/'


def _rezervace_local(salon):
    return _dev_localhost_url(int(salon.pk))


def _rezervace_staging(salon):
    web = _web_staging(salon)
    return f'{web}rezervace.html' if web else ''


def _je_staging():
    env = (getattr(settings, 'SENTRY_ENVIRONMENT', '') or '').lower()
    if env == 'staging':
        return True
    api = (getattr(settings, 'API_PUBLIC_BASE_URL', '') or '').lower()
    return 'staging' in api


def prostredi_navesti():
    if settings.DEBUG:
        return 'Lokál'
    if _je_staging():
        return 'Staging'
    return 'LIVE'


def karty_testovacich_pristupu(nove_heslo_salon_id=None, nove_heslo=''):
    from salons.models import Salon

    salony = (
        Salon.objects.filter(partner_nastaveni__je_testovaci=True)
        .select_related('partner_nastaveni', 'partner_nastaveni__kam')
        .prefetch_related('zamestnanci', 'moduly__modul')
        .order_by('name')
    )
    karty = []
    for salon in salony:
        majitel = (
            salon.zamestnanci.filter(role=Zamestnanec.ROLE_MAJITEL)
            .order_by('id')
            .first()
        )
        email = ''
        if majitel:
            email = (majitel.prihlasovaci_jmeno or '').strip()
            if '@' not in email:
                try:
                    email = majitel.flow_ucet.email or email
                except Exception:
                    pass
        modul = partner_modul(salon, MODUL_MATERIALNIK)
        materialnik = bool(modul and modul.status == PartnerModul.STAV_ACTIVE)
        karty.append({
            'salon': salon,
            'partner': salon.partner_nastaveni,
            'majitel': majitel,
            'email': email,
            'web_local': _web_local(salon),
            'web_staging': _web_staging(salon),
            'rezervace_local': _rezervace_local(salon),
            'rezervace_staging': _rezervace_staging(salon),
            'flow_local': FLOW_LOCAL,
            'flow_staging': FLOW_STAGING,
            'materialnik': materialnik,
            'sklad_local': SKLAD_LOCAL,
            'sklad_staging': SKLAD_STAGING,
            'nove_heslo': nove_heslo if nove_heslo_salon_id == salon.id else '',
        })
    return karty
