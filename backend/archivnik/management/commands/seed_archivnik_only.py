from django.core.management.base import BaseCommand

from archivnik.models import ObjectType
from flow.models import FlowUser
from partner_admin.models import MODUL_ARCHIVNIK
from partner_admin.services import vytvor_noveho_partnera
from partner_admin.services_moduly import nastav_modul
from rezervace.models import Zamestnanec

OWNER_EMAIL = 'archivnik.solo@ulov.local'
OWNER_PASSWORD = 'majitelka123'
SALON_NAME = 'Archivník sólo'


class Actor:
    username = 'archivnik-seed'


class Command(BaseCommand):
    help = 'Idempotentní Archivník-only provozovna bez aktivního FLOW.'

    def handle(self, *args, **options):
        actor = Actor()
        owner = Zamestnanec.objects.filter(
            prihlasovaci_jmeno__iexact=OWNER_EMAIL,
            role=Zamestnanec.ROLE_MAJITEL,
        ).first()
        if owner:
            salon = owner.salon
            owner.set_password(OWNER_PASSWORD)
            owner.aktivni = True
            owner.save(update_fields=['password_hash', 'aktivni'])
        else:
            salon, _partner, owner, _flow = vytvor_noveho_partnera(
                data={
                    'name': SALON_NAME,
                    'email': OWNER_EMAIL,
                    'majitel_email': OWNER_EMAIL,
                    'majitel_heslo': OWNER_PASSWORD,
                    'aktivovat_flow': False,
                    'je_testovaci': True,
                    'tarif': 'Archivník',
                },
                actor=actor,
            )
            owner.jmeno = 'Majitel Archivník'
            owner.save(update_fields=['jmeno'])

        if salon.name != SALON_NAME:
            salon.name = SALON_NAME
            salon.save(update_fields=['name'])

        partner = salon.partner_nastaveni
        partner.je_testovaci = True
        if not partner.tarif:
            partner.tarif = 'Archivník'
        partner.save()

        FlowUser.objects.filter(salon=salon).update(aktivni=False)
        nastav_modul(salon, MODUL_ARCHIVNIK, True, actor)
        ObjectType.objects.get_or_create(
            salon=salon,
            nazev='Objekt',
            defaults={'poradi': 0, 'aktivni': True},
        )
        flow_count = FlowUser.objects.filter(salon=salon, aktivni=True).count()
        self.stdout.write(
            f'salon_id={salon.id} email={OWNER_EMAIL} flow_active={flow_count} '
            f'modul=archivnik'
        )
