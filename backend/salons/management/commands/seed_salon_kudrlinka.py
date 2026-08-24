"""Salon Kudrlinka (pk 19) — čisté demo k ukázce zakládání od nuly."""

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.db import transaction

from rezervace.models import RezervacniNastaveni, Zamestnanec
from salons.models import Salon

SALON_PK = 19
OWNER_EMAIL = 'majitel.salon19@ulov.local'
OWNER_PASSWORD = 'majitelka123'
LOCAL_URL = 'http://localhost:5518/salon19/'
STAGING_URL = 'https://www.staging.ulovklienty.cz/salon19/'
LIVE_URL = 'https://www.ulovklienty.cz/salon19/'


def _env() -> str:
    return (getattr(settings, 'SENTRY_ENVIRONMENT', '') or '').lower()


def _public_url() -> str:
    if settings.DEBUG:
        return LOCAL_URL
    if _env() == 'staging':
        return STAGING_URL
    return LIVE_URL


class Command(BaseCommand):
    help = 'Vytvoří prázdné demo Salon Kudrlinka (pk 19)'

    def handle(self, *args, **options):
        existing = Salon.objects.filter(pk=SALON_PK).first()
        if existing:
            if existing.name != 'Salon Kudrlinka':
                self.stdout.write(self.style.ERROR(
                    f'PK {SALON_PK} už patří salonu „{existing.name}“. Nic neměním.'
                ))
                return
            self.stdout.write(self.style.WARNING(
                'Salon Kudrlinka už existuje, přeskakuji. '
                f'Majitelka: {OWNER_EMAIL} / {OWNER_PASSWORD}. '
                f'Web: {_public_url()}'
            ))
            return

        with transaction.atomic():
            salon = Salon(
                pk=SALON_PK,
                name='Salon Kudrlinka',
                description='',
                address='',
                phone='',
                email='',
            )
            salon.save()

            RezervacniNastaveni.objects.create(
                salon=salon,
                interval_minut=15,
                min_predstih_hodin=2,
                max_predstih_mesicu=3,
                storno_do_hodin=24,
                auto_potvrzeni=True,
                notifikace=[{'offset': '+24', 'aktivni': True}, {'offset': '-2', 'aktivni': True}],
                email_odesilatel='',
                email_jmeno_odesilatele=salon.name,
                web_rezervace_url=f'{_public_url()}rezervace.html',
            )

            Zamestnanec.objects.create(
                salon=salon,
                jmeno='Majitelka',
                specializace='',
                role='majitel',
                prihlasovaci_jmeno=OWNER_EMAIL,
                password_hash=make_password(OWNER_PASSWORD),
                zobrazit_na_webu=False,
                aktivni=True,
                poradi=999,
            )

        self.stdout.write(self.style.SUCCESS(
            f'Salon Kudrlinka vytvořen (pk={SALON_PK}). '
            f'Čistý start: bez ceníku, fotek, týmu i otevírací doby. '
            f'Majitelka: {OWNER_EMAIL} / {OWNER_PASSWORD}. '
            f'Web: {_public_url()}'
        ))
