"""Jedna interní služba pro dokončení rezervace (FLOW i web-admin)."""

from __future__ import annotations

import hashlib
import logging

from django.db import IntegrityError
from django.utils import timezone

from rezervace.models import Rezervace
from rezervace.serializers import AdminRezervaceSerializer

logger = logging.getLogger(__name__)

KONECNE_STAVY = ('zakaznik_storno', 'salon_storno', 'dokonceno', 'no_show')


class NelzeDokoncit(ValueError):
    pass


def oznacit_dokonceno(rezervace, *, log_fn=None):
    """
    Uloží stav dokonceno. Materiálník se volá jen přes outbox a jen když je modul aktivní.
    Selhání outboxu rezervaci nevrací.
    """
    if rezervace.stav in KONECNE_STAVY:
        raise NelzeDokoncit('Tuto rezervaci nelze dokončit.')

    pred = AdminRezervaceSerializer(rezervace).data
    rezervace.stav = 'dokonceno'
    if not rezervace.dokonceno_at:
        rezervace.dokonceno_at = timezone.now()
    rezervace.save(update_fields=['stav', 'dokonceno_at', 'aktualizovano'])
    po = AdminRezervaceSerializer(rezervace).data
    if log_fn:
        log_fn(rezervace, pred, po)
    try:
        enqueue_service_completed(rezervace)
    except Exception:  # noqa: BLE001 — rezervace už platí
        logger.exception(
            'Outbox service.completed selhal (rezervace %s)', rezervace.pk,
        )
    return rezervace, po


def service_completed_event_id(rezervace):
    occurred = rezervace.dokonceno_at or timezone.now()
    raw = (
        f'modernik-flow|{rezervace.salon_id}|{rezervace.pk}|completed|'
        f'{occurred.isoformat()}'
    )
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def enqueue_service_completed(rezervace):
    from partner_admin.models import MODUL_MATERIALNIK, IntegrationOutbox, PartnerModul
    from partner_admin.services_moduly import partner_modul

    row = partner_modul(rezervace.salon, MODUL_MATERIALNIK)
    if not row or row.status != PartnerModul.STAV_ACTIVE:
        return None

    partner = rezervace.salon.partner_nastaveni
    polozky = list(rezervace.polozky.select_related('sluzba').all())
    payload = {
        'event_id': service_completed_event_id(rezervace),
        'event_type': 'service.completed',
        'spec_version': '1.0',
        'occurred_at': (rezervace.dokonceno_at or timezone.now()).isoformat(),
        'source': 'modernik-flow',
        'tenant_uuid': str(partner.tenant_uuid),
        'tenant_external_id': f'salon:{rezervace.salon_id}',
        'payload': {
            'reservation_ref': f'rezervace:{rezervace.pk}',
            'completed_at': (rezervace.dokonceno_at or timezone.now()).isoformat(),
            'services': [
                {
                    'external_service_id': f'cenik:{p.sluzba_id}',
                    'name': p.sluzba.nazev,
                    'quantity': 1,
                }
                for p in polozky
            ],
        },
    }
    try:
        return IntegrationOutbox.objects.create(
            salon=rezervace.salon,
            event_id=payload['event_id'],
            event_type='service.completed',
            payload=payload,
        )
    except IntegrityError:
        return IntegrationOutbox.objects.filter(event_id=payload['event_id']).first()
