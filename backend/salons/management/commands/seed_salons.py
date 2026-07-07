from datetime import time

from django.core.management.base import BaseCommand

from salons.models import CenikPolozka, Novinka, OteviraciDoba, Salon


class Command(BaseCommand):
    help = 'Naplní databázi ukázkovými daty pro dva salony'

    def handle(self, *args, **options):
        if Salon.objects.exists():
            self.stdout.write(self.style.WARNING('Data již existují, přeskakuji.'))
            return

        salon1 = Salon.objects.create(
            name='Salon Elegance',
            description='Dámský kadeřnický salon v centru města. Nabízíme střihy, barvení a péči o vlasy.',
            address='Hlavní 12, Praha 1',
            phone='+420 123 456 789',
            email='info@salon-elegance.cz',
        )
        salon2 = Salon.objects.create(
            name='Studio Krása',
            description='Moderní kosmetický salon s relaxační atmosférou. Manikúra, pedikúra a kosmetika.',
            address='Náměstí 5, Brno',
            phone='+420 987 654 321',
            email='kontakt@studio-krasa.cz',
        )

        for salon, items in [
            (salon1, [
                ('Střih dámský', 450), ('Střih pánský', 350),
                ('Barvení', 1200), ('Melíry', 1800), ('Foukaná', 250),
            ]),
            (salon2, [
                ('Manikúra', 400), ('Pedikúra', 550),
                ('Holení obočí', 150), ('Líčení', 800), ('Masáž obličeje', 600),
            ]),
        ]:
            for i, (nazev, cena) in enumerate(items):
                CenikPolozka.objects.create(salon=salon, nazev=nazev, cena=cena, poradi=i)

        for salon, novinky in [
            (salon1, [
                ('Letní sleva 20 %', 'Po celý červen sleva na barvení vlasů.'),
                ('Nový stylista', 'Vítáme v týmu Petra – specialistu na melíry.'),
            ]),
            (salon2, [
                ('Otevírací doba v létě', 'V červenci a srpnu otevřeno i v sobotu.'),
                ('Dárkové poukazy', 'Obdarujte své blízké voucherem na kosmetiku.'),
            ]),
        ]:
            for nadpis, text in novinky:
                Novinka.objects.create(salon=salon, nadpis=nadpis, text=text)

        hours = [
            (0, time(9, 0), time(18, 0), False),
            (1, time(9, 0), time(18, 0), False),
            (2, time(9, 0), time(18, 0), False),
            (3, time(9, 0), time(18, 0), False),
            (4, time(9, 0), time(18, 0), False),
            (5, time(9, 0), time(14, 0), False),
            (6, None, None, True),
        ]
        for salon in [salon1, salon2]:
            for den, od, do, zavreno in hours:
                OteviraciDoba.objects.create(
                    salon=salon, den=den, od=od, do=do, zavreno=zavreno
                )

        self.stdout.write(self.style.SUCCESS('Vytvořeny salony 1 a 2 s ukázkovými daty.'))
