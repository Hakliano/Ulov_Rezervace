"""Salon „U dvou přátel“ (ID 4) — Juan & Duran, dva rovnocenní kadeřníci."""

from datetime import time

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand

from rezervace.models import RezervacniNastaveni, Zamestnanec, ZamestnanecRozvrh
from salons.models import CenikPolozka, Novinka, OteviraciDoba, Salon

DURATION_MAP = {
    'Coupe classique': (35, 10),
    'Barbe & contours': (25, 5),
    'Coloration douce': (90, 15),
    'Mèches café au lait': (120, 15),
    'Brushing parisien': (30, 5),
    'Soin profond': (45, 10),
    'Rasage à l\'ancienne': (30, 5),
    'Forfait du jour': (60, 10),
}


class Command(BaseCommand):
    help = 'Vytvoří salon U dvou přátel (pk 4) — Juan, Duran, technický správce'

    def handle(self, *args, **options):
        if Salon.objects.filter(name__icontains='dvou přátel').exists():
            self.stdout.write(self.style.WARNING('Salon U dvou přátel už existuje, přeskakuji.'))
            return

        salon = Salon.objects.create(
            name='U dvou přátel',
            description=(
                'Malá francouzská kavárna a kadeřnictví v jednom. Dva přátelé, dva křesla, '
                'espresso mezi střihy. Juan a Duran — každý svůj mistr, žádný šéf nad šéfem.'
            ),
            address='Rue des Amis 2, Praha 2',
            phone='+420 222 333 444',
            email='bonjour@udvoupratel.cz',
        )

        services = [
            ('Coupe classique', 520),
            ('Barbe & contours', 380),
            ('Coloration douce', 1450),
            ('Mèches café au lait', 1890),
            ('Brushing parisien', 350),
            ('Soin profond', 590),
            ('Rasage à l\'ancienne', 420),
            ('Forfait du jour', 990),
        ]
        for i, (nazev, cena) in enumerate(services):
            dur = DURATION_MAP.get(nazev, (40, 10))
            CenikPolozka.objects.create(
                salon=salon, nazev=nazev, cena=cena, poradi=i,
                delka_minut=dur[0], rezerva_minut=dur[1], aktivni=True,
            )

        for nadpis, text in [
            ('Nouveau menu du jour', 'Každý čtvrtek jiný forfait — espresso v ceně.'),
            ('Juan & Duran', 'Dva kadeřníci, jedna kavárna. Rezervujte konkrétního mistra.'),
        ]:
            Novinka.objects.create(salon=salon, nadpis=nadpis, text=text)

        hours = [
            (0, None, None, True),
            (1, time(9, 0), time(18, 0), False),
            (2, time(9, 0), time(18, 0), False),
            (3, time(9, 0), time(20, 0), False),
            (4, time(9, 0), time(20, 0), False),
            (5, time(9, 0), time(20, 0), False),
            (6, time(10, 0), time(16, 0), False),
        ]
        for den, od, do, zavreno in hours:
            OteviraciDoba.objects.create(salon=salon, den=den, od=od, do=do, zavreno=zavreno)

        RezervacniNastaveni.objects.create(
            salon=salon,
            interval_minut=15,
            min_predstih_hodin=2,
            max_predstih_mesicu=2,
            storno_do_hodin=24,
            auto_potvrzeni=True,
            notifikace=[{'offset': '+24', 'aktivni': True}, {'offset': '-2', 'aktivni': True}],
            email_odesilatel=salon.email,
            email_jmeno_odesilatele=salon.name,
            web_rezervace_url='http://localhost:5503/rezervace.html',
        )

        # Technický správce salonu (web, nastavení, rozvrhy) — není Juan ani Duran
        Zamestnanec.objects.create(
            salon=salon,
            jmeno='Správce salonu',
            specializace='',
            role='majitel',
            prihlasovaci_jmeno='spravce',
            password_hash=make_password('spravce123'),
            zobrazit_na_webu=False,
            aktivni=True,
            poradi=999,
        )

        staff_data = [
            ('Juan', 'juan', 'Střihy, barvy, francouzská elegance', [
                (0, None, None, True),
                (1, time(9, 0), time(18, 0), False),
                (2, time(9, 0), time(18, 0), False),
                (3, None, None, True),
                (4, time(9, 0), time(20, 0), False),
                (5, time(9, 0), time(20, 0), False),
                (6, time(10, 0), time(14, 0), False),
            ]),
            ('Duran', 'duran', 'Holení, contours, pánské střihy', [
                (0, None, None, True),
                (1, time(10, 0), time(19, 0), False),
                (2, time(10, 0), time(19, 0), False),
                (3, time(9, 0), time(20, 0), False),
                (4, time(9, 0), time(20, 0), False),
                (5, None, None, True),
                (6, time(10, 0), time(16, 0), False),
            ]),
        ]
        for poradi, (jmeno, login, spec, rozvrh) in enumerate(staff_data):
            z = Zamestnanec.objects.create(
                salon=salon,
                jmeno=jmeno,
                specializace=spec,
                role='zamestnanec',
                prihlasovaci_jmeno=login,
                password_hash=make_password(f'{login}123'),
                zobrazit_na_webu=True,
                aktivni=True,
                poradi=poradi,
            )
            for den, od, do, volno in rozvrh:
                ZamestnanecRozvrh.objects.create(
                    zamestnanec=z, den=den, od=od, do=do, volno=volno,
                )

        self.stdout.write(self.style.SUCCESS(
            f'Salon U dvou přátel vytvořen (pk={salon.pk}).\n'
            f'  Juan: juan / juan123  |  Duran: duran / duran123  (jen vlastní kalendář)\n'
            f'  Správce (web + nastavení): spravce / spravce123\n'
            f'  Frontend: http://localhost:5503'
        ))
