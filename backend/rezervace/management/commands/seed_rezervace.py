from datetime import time

from django.core.management.base import BaseCommand

from rezervace.models import RezervacniNastaveni, StatniSvatky, Zamestnanec, ZamestnanecRozvrh
from salons.models import CenikPolozka, Salon


DURATION_MAP = {
    'Střih dámský': (45, 10),
    'Střih pánský': (30, 5),
    'Barvení': (120, 15),
    'Melíry': (150, 15),
    'Foukaná': (30, 5),
    'Manikúra': (60, 10),
    'Pedikúra': (75, 10),
    'Holení obočí': (20, 5),
    'Líčení': (60, 10),
    'Masáž obličeje': (45, 10),
}


class Command(BaseCommand):
    help = 'Naplní rezervační data pro salony (nastavení, zaměstnanci, délky služeb)'

    def handle(self, *args, **options):
        for salon in Salon.objects.all():
            port = 5499 + salon.pk
            default_url = f'http://localhost:{port}/rezervace.html'
            nast, _ = RezervacniNastaveni.objects.get_or_create(
                salon=salon,
                defaults={
                    'interval_minut': 15,
                    'min_predstih_hodin': 2,
                    'max_predstih_mesicu': 3,
                    'storno_do_hodin': 24,
                    'auto_potvrzeni': True,
                    'notifikace': [
                        {
                            'offset': '+24',
                            'aktivni': True,
                        },
                        {
                            'offset': '-2',
                            'aktivni': True,
                        },
                    ],
                    'email_odesilatel': salon.email,
                    'email_jmeno_odesilatele': salon.name,
                    'web_rezervace_url': default_url,
                },
            )
            if not nast.email_odesilatel:
                nast.email_odesilatel = salon.email
                nast.email_jmeno_odesilatele = salon.name
                nast.save(update_fields=['email_odesilatel', 'email_jmeno_odesilatele'])
            if not nast.web_rezervace_url:
                nast.web_rezervace_url = default_url
                nast.save(update_fields=['web_rezervace_url'])

            for polozka in salon.cenik.all():
                dur = DURATION_MAP.get(polozka.nazev, (30, 5))
                polozka.delka_minut = dur[0]
                polozka.rezerva_minut = dur[1]
                polozka.aktivni = True
                polozka.save()

        self._seed_zamestnanci_salon1()
        self._seed_zamestnanci_salon2()
        self._seed_svatky()
        self.stdout.write(self.style.SUCCESS('Rezervační data vytvořena.'))

    def _seed_zamestnanci_salon1(self):
        try:
            salon = Salon.objects.get(pk=1)
        except Salon.DoesNotExist:
            return
        if salon.zamestnanci.exists():
            return

        staff = [
            ('Petra', 'Pánské střihy, melíry', [
                (0, time(8, 0), time(16, 0), False),
                (1, None, None, True),
                (2, time(10, 0), time(18, 0), False),
                (3, time(8, 0), time(16, 0), False),
                (4, time(8, 0), time(16, 0), False),
                (5, time(9, 0), time(13, 0), False),
                (6, None, None, True),
            ]),
            ('Jana', 'Barvení, dámské střihy', [
                (0, time(12, 0), time(20, 0), False),
                (1, time(8, 0), time(16, 0), False),
                (2, time(8, 0), time(16, 0), False),
                (3, time(10, 0), time(18, 0), False),
                (4, time(8, 0), time(16, 0), False),
                (5, None, None, True),
                (6, None, None, True),
            ]),
            ('Lenka', 'Svatební účesy, foukaná', [
                (0, time(9, 0), time(17, 0), False),
                (1, time(9, 0), time(17, 0), False),
                (2, None, None, True),
                (3, time(9, 0), time(17, 0), False),
                (4, time(9, 0), time(17, 0), False),
                (5, time(9, 0), time(14, 0), False),
                (6, None, None, True),
            ]),
        ]
        for i, (jmeno, spec, rozvrh) in enumerate(staff):
            z = Zamestnanec.objects.create(
                salon=salon, jmeno=jmeno, specializace=spec, poradi=i,
            )
            for den, od, do, volno in rozvrh:
                ZamestnanecRozvrh.objects.create(
                    zamestnanec=z, den=den, od=od, do=do, volno=volno,
                )

    def _seed_zamestnanci_salon2(self):
        try:
            salon = Salon.objects.get(pk=2)
        except Salon.DoesNotExist:
            return
        if salon.zamestnanci.exists():
            return

        staff = [
            ('Markéta', 'Manikúra, pedikúra', [
                (0, time(9, 0), time(17, 0), False),
                (1, time(9, 0), time(17, 0), False),
                (2, time(9, 0), time(17, 0), False),
                (3, None, None, True),
                (4, time(9, 0), time(17, 0), False),
                (5, time(9, 0), time(14, 0), False),
                (6, None, None, True),
            ]),
            ('Eva', 'Kosmetika, masáže', [
                (0, time(10, 0), time(18, 0), False),
                (1, None, None, True),
                (2, time(10, 0), time(18, 0), False),
                (3, time(10, 0), time(18, 0), False),
                (4, time(10, 0), time(18, 0), False),
                (5, time(9, 0), time(14, 0), False),
                (6, None, None, True),
            ]),
        ]
        for i, (jmeno, spec, rozvrh) in enumerate(staff):
            z = Zamestnanec.objects.create(
                salon=salon, jmeno=jmeno, specializace=spec, poradi=i,
            )
            for den, od, do, volno in rozvrh:
                ZamestnanecRozvrh.objects.create(
                    zamestnanec=z, den=den, od=od, do=do, volno=volno,
                )

    def _seed_svatky(self):
        svatky = [
            ('2026-01-01', 'Nový rok'),
            ('2026-05-01', 'Svátek práce'),
            ('2026-05-08', 'Den vítězství'),
            ('2026-07-05', 'Den slovanských věrozvěstů Cyrila a Metoděje'),
            ('2026-07-06', 'Den upálení mistra Jana Husa'),
            ('2026-09-28', 'Den české státnosti'),
            ('2026-10-28', 'Den vzniku samostatného československého státu'),
            ('2026-11-17', 'Den boje za svobodu a demokracii'),
            ('2026-12-24', 'Štědrý den'),
            ('2026-12-25', '1. svátek vánoční'),
            ('2026-12-26', '2. svátek vánoční'),
        ]
        from datetime import datetime
        for d, nazev in svatky:
            StatniSvatky.objects.get_or_create(
                datum=datetime.strptime(d, '%Y-%m-%d').date(),
                defaults={'nazev': nazev},
            )
