"""Katalog modulů — aktivace / deaktivace bez boolean sloupců na partnerovi."""

from __future__ import annotations

import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .materialnik_client import (
    MaterialnikRejected,
    MaterialnikUnavailable,
    deactivate_tenant,
    provision_tenant,
)
from .entitlements import (
    FEATURE_ARCHIVNIK,
    FEATURE_MATERIALNIK,
    MODUL_NA_FEATURE,
    ModulNeniVNaroku,
    features_planu,
    plan_partnera,
    partner_ma,
)
from .models import (
    MODUL_ARCHIVNIK,
    MODUL_MATERIALNIK,
    ModulKatalog,
    PartnerFeatureGrant,
    PartnerModul,
)
from .services import log_superadmin

logger = logging.getLogger(__name__)


def partner_modul(salon, kod=MODUL_MATERIALNIK):
    return (
        PartnerModul.objects.select_related('modul')
        .filter(salon=salon, modul__kod=kod)
        .first()
    )


def modul_je_aktivni(salon_id, kod=MODUL_MATERIALNIK):
    return PartnerModul.objects.filter(
        salon_id=salon_id,
        modul__kod=kod,
        status=PartnerModul.STAV_ACTIVE,
    ).exists()


def materialnik_je_aktivni(salon):
    """Technická aktivace Materiálníku (PartnerModul), ne produktový nárok."""
    return modul_je_aktivni(getattr(salon, 'pk', salon), MODUL_MATERIALNIK)


def materialnik_pro_me(salon):
    """Do /api/flow/me/ — URL jen při nároku i aktivním modulu."""
    from .entitlements import materialnik_smí_fungovat

    if not partner_ma(salon, FEATURE_MATERIALNIK):
        class _Actor:
            username = 'materialnik-narok'
        znepristupni_materialnik_bez_mazani(salon, _Actor())
        return None
    if not materialnik_smí_fungovat(salon):
        return None
    url = (getattr(settings, 'MATERIALNIK_PUBLIC_URL', '') or '').rstrip('/')
    return {'url': url}


def archivnik_je_aktivni(salon):
    """Technická aktivace Archivníka (PartnerModul), ne produktový nárok."""
    return modul_je_aktivni(getattr(salon, 'pk', salon), MODUL_ARCHIVNIK)


def archivnik_pro_me(salon):
    """Do /api/flow/me/ — URL jen když je nárok i modul aktivní."""
    if not partner_ma(salon, FEATURE_ARCHIVNIK) or not archivnik_je_aktivni(salon):
        return None
    url = (getattr(settings, 'ARCHIVNIK_PUBLIC_URL', '') or '/archivnik/').rstrip('/') + '/'
    return {'url': url}


def zajisti_archivnik_pro_modernik(salon, actor):
    """Zapne Archivník jen při nároku. FLOW samo o sobě nárok nedává.

    Idempotentní, nemaže data. Existující vypnutí adminem se nepřepisuje.
    """
    if not partner_ma(salon, FEATURE_ARCHIVNIK):
        return partner_modul(salon, MODUL_ARCHIVNIK)
    row = partner_modul(salon, MODUL_ARCHIVNIK)
    if row is not None and row.status != PartnerModul.STAV_ACTIVE:
        return row
    return nastav_modul(salon, MODUL_ARCHIVNIK, True, actor)


def aplikuj_vychozi_moduly_planu(salon, actor):
    """Nový PRO: Archivník i Materiálník ON. Nový START: oba OFF."""
    if partner_ma(salon, FEATURE_ARCHIVNIK):
        nastav_modul(salon, MODUL_ARCHIVNIK, True, actor)
    if partner_ma(salon, FEATURE_MATERIALNIK):
        nastav_modul(salon, MODUL_MATERIALNIK, True, actor)


def znepristupni_archivnik_bez_mazani(salon, actor):
    """Vypne PartnerModul Archivník. Data Kartotéky se nemažou."""
    row = partner_modul(salon, MODUL_ARCHIVNIK)
    if row is None or row.status == PartnerModul.STAV_INACTIVE:
        return row
    return nastav_modul(salon, MODUL_ARCHIVNIK, False, actor)


def znepristupni_materialnik_bez_mazani(salon, actor):
    """Vypne PartnerModul Materiálník. Data skladu se nemažou."""
    row = partner_modul(salon, MODUL_MATERIALNIK)
    if row is None or row.status == PartnerModul.STAV_INACTIVE:
        return row
    return nastav_modul(salon, MODUL_MATERIALNIK, False, actor)


def znepristupni_materialnik_pokud_neni_narok(salon, actor):
    """START bez platného nároku: modul INACTIVE. Grant ponechá modul beze změny."""
    if partner_ma(salon, FEATURE_MATERIALNIK):
        return partner_modul(salon, MODUL_MATERIALNIK)
    return znepristupni_materialnik_bez_mazani(salon, actor)


def platny_materialnik_grant(salon, ted=None):
    qs = PartnerFeatureGrant.objects.filter(
        salon=salon,
        feature=FEATURE_MATERIALNIK,
        zakaz=False,
        aktivni=True,
    ).order_by('-vytvoreno')
    for grant in qs:
        if grant.je_platny(ted):
            return grant
    return None


def povol_materialnik_individulne(salon, actor, platnost_do=None):
    """Grant materialnik + aktivace modulu. Nemění plan."""
    ted = timezone.now()
    grant = platny_materialnik_grant(salon, ted)
    zdroj = (
        PartnerFeatureGrant.ZDROJ_TRIAL
        if platnost_do
        else PartnerFeatureGrant.ZDROJ_VYJIMKA
    )
    if grant is None:
        grant = (
            PartnerFeatureGrant.objects.filter(
                salon=salon,
                feature=FEATURE_MATERIALNIK,
                zakaz=False,
            )
            .order_by('-vytvoreno')
            .first()
        )
        if grant is None:
            grant = PartnerFeatureGrant(
                salon=salon,
                feature=FEATURE_MATERIALNIK,
                zakaz=False,
            )
        grant.aktivni = True
        grant.zakaz = False
        grant.platnost_od = None
        grant.platnost_do = platnost_do
        grant.zdroj = zdroj
        grant.poznamka = grant.poznamka or 'Individuální povolení Materiálníku'
        grant.save()
    elif platnost_do is not None:
        grant.platnost_do = platnost_do
        grant.zdroj = zdroj
        grant.save(update_fields=['platnost_do', 'zdroj', 'aktualizovano'])
    return nastav_modul(salon, MODUL_MATERIALNIK, True, actor)


def odeber_materialnik_grant(salon, actor):
    """Deaktivuje individuální granty materialnik a znepřístupní modul. Data se nemažou."""
    PartnerFeatureGrant.objects.filter(
        salon=salon,
        feature=FEATURE_MATERIALNIK,
        zakaz=False,
        aktivni=True,
    ).update(aktivni=False)
    return znepristupni_materialnik_bez_mazani(salon, actor)


def materialnik_admin_ctx(salon):
    """Podklady pro kartu Materiálníku v detailu partnera."""
    z_planu = FEATURE_MATERIALNIK in features_planu(plan_partnera(salon))
    grant = platny_materialnik_grant(salon)
    return {
        'narok': partner_ma(salon, FEATURE_MATERIALNIK),
        'z_planu': z_planu,
        'grant': grant,
        'individualni': bool(grant) and not z_planu,
    }


@transaction.atomic
def nastav_modul(salon, kod, zapnout, actor):
    if zapnout:
        feature = MODUL_NA_FEATURE.get(kod)
        if feature and not partner_ma(salon, feature):
            raise ModulNeniVNaroku(feature, salon=salon)
    katalog = ModulKatalog.objects.get(kod=kod)
    row, _ = PartnerModul.objects.select_for_update().get_or_create(
        salon=salon,
        modul=katalog,
        defaults={'status': PartnerModul.STAV_INACTIVE},
    )
    if zapnout:
        return _zapnout(salon, row, actor)
    return _vypnout(salon, row, actor)


def _je_materialnik(row):
    return row.modul.kod == MODUL_MATERIALNIK


def _zapnout_lokalni_modul(salon, row, actor):
    """Zapnutí modulu bez vzdáleného provisioningu (Archivník, budoucí moduly)."""
    row.status = PartnerModul.STAV_ACTIVE
    row.provisioning_error = ''
    row.activated_at = timezone.now()
    row.deactivated_at = None
    row.save(update_fields=[
        'status', 'provisioning_error', 'activated_at', 'deactivated_at', 'aktualizovano',
    ])
    log_superadmin(
        salon,
        actor,
        f'{row.modul.nazev} zapnut.',
        po={'status': row.status},
    )
    return row


def _zapnout(salon, row, actor):
    if row.status == PartnerModul.STAV_ACTIVE:
        return row

    if not _je_materialnik(row):
        return _zapnout_lokalni_modul(salon, row, actor)

    partner = salon.partner_nastaveni
    row.status = PartnerModul.STAV_PENDING
    row.provisioning_error = ''
    row.save(update_fields=['status', 'provisioning_error', 'aktualizovano'])

    try:
        data = provision_tenant(
            tenant_uuid=partner.tenant_uuid,
            salon_id=salon.id,
            name=salon.name,
        )
    except (MaterialnikUnavailable, MaterialnikRejected) as exc:
        row.status = PartnerModul.STAV_ERROR
        row.provisioning_error = str(exc.detail)[:2000]
        row.save(update_fields=['status', 'provisioning_error', 'aktualizovano'])
        log_superadmin(
            salon,
            actor,
            f'Materiálník se nepodařilo zapnout: {row.provisioning_error[:180]}',
            pred={'status': PartnerModul.STAV_INACTIVE},
            po={'status': row.status},
        )
        return row

    hmac_key = (data or {}).get('hmac_key') or row.hmac_key
    row.hmac_key = hmac_key or row.hmac_key
    row.status = PartnerModul.STAV_ACTIVE
    row.provisioning_error = ''
    row.activated_at = timezone.now()
    row.deactivated_at = None
    row.save(update_fields=[
        'hmac_key', 'status', 'provisioning_error',
        'activated_at', 'deactivated_at', 'aktualizovano',
    ])
    log_superadmin(
        salon,
        actor,
        'Materiálník zapnut.',
        po={'status': row.status, 'tenant_uuid': str(partner.tenant_uuid)},
    )
    return row


def _vypnout(salon, row, actor):
    if row.status == PartnerModul.STAV_INACTIVE:
        return row

    pred = row.status
    if _je_materialnik(row):
        partner = salon.partner_nastaveni
        try:
            deactivate_tenant(tenant_uuid=partner.tenant_uuid)
        except (MaterialnikUnavailable, MaterialnikRejected) as exc:
            logger.warning('Deaktivace Materiálníku na dálku selhala: %s', exc)

    row.status = PartnerModul.STAV_INACTIVE
    row.deactivated_at = timezone.now()
    row.provisioning_error = ''
    row.save(update_fields=['status', 'deactivated_at', 'provisioning_error', 'aktualizovano'])
    log_superadmin(
        salon,
        actor,
        f'{row.modul.nazev} vypnut.',
        pred={'status': pred},
        po={'status': row.status},
    )
    return row
