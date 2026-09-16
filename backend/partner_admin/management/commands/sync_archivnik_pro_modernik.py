#!/usr/bin/env python3
"""P5.4 — u partnerů s FLOW (Moderník) zapne PartnerModul archivnik.

Idempotentní. Nemaže Obory, ObjectTypes, CustomFields, data kartotéky
ani ostatní PartnerModul. Standalone Archivník bez FLOW nemění.
"""
from django.core.management.base import BaseCommand

from flow.models import FlowUser
from partner_admin.models import MODUL_ARCHIVNIK, PartnerModul
from partner_admin.services_moduly import zajisti_archivnik_pro_modernik
from salons.models import Salon


class Actor:
    username = 'p54-sync'


class Command(BaseCommand):
    help = (
        'Zapne Archivník u salonů, které mají aktivní FLOW účet. '
        'Bez plošného resetu konfigurace.'
    )

    def handle(self, *args, **options):
        salon_ids = list(
            FlowUser.objects.filter(aktivni=True)
            .values_list('salon_id', flat=True)
            .distinct()
        )
        zapnuto = 0
        uz_aktivni = 0
        for salon in Salon.objects.filter(pk__in=salon_ids).order_by('id'):
            bylo = PartnerModul.objects.filter(
                salon=salon,
                modul__kod=MODUL_ARCHIVNIK,
                status=PartnerModul.STAV_ACTIVE,
            ).exists()
            zajisti_archivnik_pro_modernik(salon, Actor())
            if bylo:
                uz_aktivni += 1
            else:
                zapnuto += 1
        self.stdout.write(
            f'P5.4 sync: zapnuto={zapnuto} uz_aktivni={uz_aktivni} '
            f'flow_salonu={len(salon_ids)}'
        )
