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
from .models import MODUL_MATERIALNIK, ModulKatalog, PartnerModul
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


def materialnik_pro_me(salon):
    """Do /api/flow/me/ — když není aktivní, nevrací nic (žádná zmínka ve FLOW)."""
    row = partner_modul(salon, MODUL_MATERIALNIK)
    if not row or not row.je_aktivni:
        return None
    url = (getattr(settings, 'MATERIALNIK_PUBLIC_URL', '') or '').rstrip('/')
    return {'url': url}


@transaction.atomic
def nastav_modul(salon, kod, zapnout, actor):
    katalog = ModulKatalog.objects.get(kod=kod)
    row, _ = PartnerModul.objects.select_for_update().get_or_create(
        salon=salon,
        modul=katalog,
        defaults={'status': PartnerModul.STAV_INACTIVE},
    )
    if zapnout:
        return _zapnout(salon, row, actor)
    return _vypnout(salon, row, actor)


def _zapnout(salon, row, actor):
    if row.status == PartnerModul.STAV_ACTIVE:
        return row

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
    partner = salon.partner_nastaveni
    try:
        deactivate_tenant(tenant_uuid=partner.tenant_uuid)
    except (MaterialnikUnavailable, MaterialnikRejected) as exc:
        logger.warning('Deaktivace Materiálníku na dálku selhala: %s', exc)
        # FLOW flag stejně vypneme — nové eventy nesmí odcházet.

    row.status = PartnerModul.STAV_INACTIVE
    row.deactivated_at = timezone.now()
    row.provisioning_error = ''
    row.save(update_fields=['status', 'deactivated_at', 'provisioning_error', 'aktualizovano'])
    log_superadmin(
        salon,
        actor,
        'Materiálník vypnut. Data skladu zůstávají.',
        pred={'status': pred},
        po={'status': row.status},
    )
    return row
