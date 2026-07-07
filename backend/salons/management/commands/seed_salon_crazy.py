"""Přidá salon CRAZY (ID 3) — jedna kadeřnice, 10 služeb, hype styl."""

from datetime import time

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand

from rezervace.models import RezervacniNastaveni, Zamestnanec, ZamestnanecRozvrh
from salons.models import CenikPolozka, Novinka, OteviraciDoba, Salon

DURATION_MAP = {
    'NEON střih': (40, 10),
    'Duha barvení': (150, 20),
    'Růžový chaos melír': (180, 20),
    'Glitter wash': (90, 15),
    'Punk sidecut': (35, 10),
    'Bláznivá foukaná': (30, 5),
    'Váleček & volume': (50, 10),
    'Express záchrana 15': (15, 5),
    'Foto-ready styling': (60, 10),
    'CRAZY full makeover': (210, 25),
}


class Command(BaseCommand):
    help = 'Vytvoří salon CRAZY (pk 3) s jednou kadeřnicí a 10 službami'

    def handle(self, *args, **options):
        if Salon.objects.filter(name__icontains='CRAZY').exists():
            self.stdout.write(self.style.WARNING('Salon CRAZY už existuje, přeskakuji.'))
            return

        salon = Salon.objects.create(
            name='CRAZY',
            description=(
                'Nejkřiklavější kadeřnictví ve městě. Jedna kadeřnice, nulové kompromisy, '
                'maximum barev a energie. Tady nejde o klidný salon — tady jde o show.'
            ),
            address='Rainbow Alley 42, Praha 7',
            phone='+420 777 420 069',
            email='ahoj@crazy-hair.cz',
        )

        services = [
            ('NEON střih', 690),
            ('Duha barvení', 2490),
            ('Růžový chaos melír', 2890),
            ('Glitter wash', 1290),
            ('Punk sidecut', 590),
            ('Bláznivá foukaná', 390),
            ('Váleček & volume', 790),
            ('Express záchrana 15', 290),
            ('Foto-ready styling', 990),
            ('CRAZY full makeover', 3490),
        ]
        for i, (nazev, cena) in enumerate(services):
            dur = DURATION_MAP.get(nazev, (45, 10))
            CenikPolozka.objects.create(
                salon=salon, nazev=nazev, cena=cena, poradi=i,
                delka_minut=dur[0], rezerva_minut=dur[1], aktivni=True,
            )

        for nadpis, text in [
            ('Otevíráme v neonové', 'Každý pátek color night — přijď v nejdivočejším outfitu.'),
            ('Nová glitter kolekce', 'Limitované třpytky do vlasů jen do vyprodání zásob.'),
            ('Solo artist Zoey', 'Jeden stůl, jedna vize, žádné fronty u více kadeřnic.'),
        ]:
            Novinka.objects.create(salon=salon, nadpis=nadpis, text=text)

        hours = [
            (0, None, None, True),
            (1, time(10, 0), time(19, 0), False),
            (2, time(10, 0), time(19, 0), False),
            (3, time(10, 0), time(21, 0), False),
            (4, time(10, 0), time(21, 0), False),
            (5, time(10, 0), time(22, 0), False),
            (6, time(11, 0), time(18, 0), False),
        ]
        for den, od, do, zavreno in hours:
            OteviraciDoba.objects.create(salon=salon, den=den, od=od, do=do, zavreno=zavreno)

        RezervacniNastaveni.objects.create(
            salon=salon,
            interval_minut=15,
            min_predstih_hodin=1,
            max_predstih_mesicu=2,
            storno_do_hodin=12,
            auto_potvrzeni=True,
            notifikace=[{'offset': '+24', 'aktivni': True}, {'offset': '-2', 'aktivni': True}],
            email_odesilatel=salon.email,
            email_jmeno_odesilatele=salon.name,
            web_rezervace_url='http://localhost:5502/rezervace.html',
        )

        majitelka = Zamestnanec.objects.create(
            salon=salon,
            jmeno='Majitelka',
            specializace='',
            role='majitel',
            prihlasovaci_jmeno='majitelka',
            password_hash=make_password('majitelka123'),
            zobrazit_na_webu=False,
            aktivni=True,
            poradi=999,
        )

        zoey = Zamestnanec.objects.create(
            salon=salon,
            jmeno='Zoey CRAZY',
            specializace='Barvy, střihy, glitter, zero chill',
            role='zamestnanec',
            prihlasovaci_jmeno='zoey',
            password_hash=make_password('zoey123'),
            zobrazit_na_webu=True,
            aktivni=True,
            poradi=0,
        )
        rozvrh = [
            (0, None, None, True),
            (1, time(10, 0), time(19, 0), False),
            (2, time(10, 0), time(19, 0), False),
            (3, time(10, 0), time(21, 0), False),
            (4, time(10, 0), time(21, 0), False),
            (5, time(10, 0), time(22, 0), False),
            (6, time(11, 0), time(18, 0), False),
        ]
        for den, od, do, volno in rozvrh:
            ZamestnanecRozvrh.objects.create(zamestnanec=zoey, den=den, od=od, do=do, volno=volno)

        self.stdout.write(self.style.SUCCESS(
            f'Salon CRAZY vytvořen (pk={salon.pk}). Kadeřnice: zoey / zoey123. '
            f'Majitelka: majitelka / majitelka123. Frontend: http://localhost:5502'
        ))
