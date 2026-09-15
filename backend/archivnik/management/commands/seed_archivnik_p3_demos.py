"""Oddělené P3 demo provozovny. Nikdy nemaže Archivník sólo ani existující kartotéku."""

from django.core.management.base import BaseCommand

from archivnik.models import Customer, Obor, ObjectType
from archivnik.services import apply_preset
from flow.models import FlowUser
from partner_admin.models import MODUL_ARCHIVNIK
from partner_admin.services import vytvor_noveho_partnera
from partner_admin.services_moduly import nastav_modul
from rezervace.models import Zamestnanec

PASSWORD = 'majitelka123'

DEMOS = [
    {
        'email': 'archivnik.vet@ulov.local',
        'name': 'Archivník vet',
        'preset': 'vet',
    },
    {
        'email': 'archivnik.pneu@ulov.local',
        'name': 'Archivník pneu',
        'preset': 'pneu',
    },
    {
        'email': 'archivnik.beauty@ulov.local',
        'name': 'Archivník beauty',
        'preset': 'beauty',
    },
    {
        'email': 'archivnik.dental@ulov.local',
        'name': 'Archivník dentální',
        'preset': None,
    },
]


class Actor:
    username = 'archivnik-p3-seed'


class Command(BaseCommand):
    help = 'Založí oddělené P3 demo provozovny. Bez wipe existujících dat.'

    def handle(self, *args, **options):
        actor = Actor()
        for spec in DEMOS:
            owner = Zamestnanec.objects.filter(
                prihlasovaci_jmeno__iexact=spec['email'],
                role=Zamestnanec.ROLE_MAJITEL,
            ).first()
            if owner:
                salon = owner.salon
                owner.set_password(PASSWORD)
                owner.aktivni = True
                owner.save(update_fields=['password_hash', 'aktivni'])
            else:
                salon, _partner, owner, _flow = vytvor_noveho_partnera(
                    data={
                        'name': spec['name'],
                        'email': spec['email'],
                        'majitel_email': spec['email'],
                        'majitel_heslo': PASSWORD,
                        'aktivovat_flow': False,
                        'je_testovaci': True,
                        'tarif': 'Archivník',
                    },
                    actor=actor,
                )
                owner.jmeno = spec['name']
                owner.save(update_fields=['jmeno'])

            if salon.name != spec['name']:
                salon.name = spec['name']
                salon.save(update_fields=['name'])
            partner = salon.partner_nastaveni
            partner.je_testovaci = True
            if not partner.tarif:
                partner.tarif = 'Archivník'
            partner.save()
            FlowUser.objects.filter(salon=salon).update(aktivni=False)
            nastav_modul(salon, MODUL_ARCHIVNIK, True, actor)

            if spec['preset'] and not Obor.objects.filter(salon=salon, zdroj_preset=spec['preset']).exists():
                if not Customer.objects.filter(salon=salon).exists():
                    apply_preset(salon, spec['preset'])
            if spec['preset'] is None:
                ObjectType.objects.filter(salon=salon, nazev='Chrup').update(vyzaduje_nazev=False)
            self.stdout.write(
                f"email={spec['email']} salon_id={salon.id} preset={spec['preset'] or '-'} "
                f"obory={Obor.objects.filter(salon=salon).count()}"
            )
