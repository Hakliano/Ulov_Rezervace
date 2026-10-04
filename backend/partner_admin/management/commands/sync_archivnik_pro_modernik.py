#!/usr/bin/env python3
"""U partnerů s FLOW a nárokem na Archivník doplní chybějící PartnerModul.

Nemění vypnutý modul (admin OFF). START bez nároku nepřepíná. Nemaže data.
Standalone Archivník bez FLOW nemění.
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
        'Doplní Archivník u salonů s FLOW, které na něj mají nárok a ještě '
        'nemají vypnutý PartnerModul. FLOW samo o sobě nárok nedává.'
    )

    def handle(self, *args, **options):
        salon_ids = list(
            FlowUser.objects.filter(aktivni=True)
            .values_list('salon_id', flat=True)
            .distinct()
        )
        zapnuto = 0
        uz_aktivni = 0
        preskoceno = 0
        for salon in Salon.objects.filter(pk__in=salon_ids).order_by('id'):
            bylo = PartnerModul.objects.filter(
                salon=salon,
                modul__kod=MODUL_ARCHIVNIK,
                status=PartnerModul.STAV_ACTIVE,
            ).exists()
            zajisti_archivnik_pro_modernik(salon, Actor())
            je = PartnerModul.objects.filter(
                salon=salon,
                modul__kod=MODUL_ARCHIVNIK,
                status=PartnerModul.STAV_ACTIVE,
            ).exists()
            if je and bylo:
                uz_aktivni += 1
            elif je and not bylo:
                zapnuto += 1
            else:
                preskoceno += 1
        self.stdout.write(
            f'P5.4 sync: zapnuto={zapnuto} uz_aktivni={uz_aktivni} '
            f'preskoceno={preskoceno} flow_salonu={len(salon_ids)}'
        )
