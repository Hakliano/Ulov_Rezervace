from datetime import time

from django.core.management.base import BaseCommand, CommandError

from rezervace.models import RezervacniNastaveni, Zamestnanec, ZamestnanecRozvrh
from salons.models import CenikPolozka, Novinka, OteviraciDoba, Salon


DEMOS = [
    {
        'pk': 9, 'name': 'Movium', 'kind': 'fyzioterapie',
        'description': 'Fyzioterapie pro volný pohyb bez bolesti.',
        'services': [('Individuální fyzioterapie', 1200, 60), ('Sportovní rehab', 1350, 60), ('Masáž', 850, 45), ('Vstupní vyšetření', 1450, 60)],
    },
    {
        'pk': 10, 'name': 'PawCare', 'kind': 'veterina',
        'description': 'Citlivá veterinární péče pro vaše zvířecí parťáky.',
        'services': [('Preventivní prohlídka', 650, 30), ('Očkování', 750, 30), ('Kastrace konzultace', 500, 30), ('Dentální hygiena zvířat', 1800, 60)],
    },
    {
        'pk': 11, 'name': 'Bělice', 'kind': 'dentální hygiena',
        'description': 'Moderní dentální hygiena pro zdravý a přirozený úsměv.',
        'services': [('Dentální hygiena', 1350, 60), ('Bělení', 2900, 75), ('Vstupní vyšetření', 650, 30), ('Airflow', 750, 30)],
    },
    {
        'pk': 12, 'name': 'VodaPro', 'kind': 'instalatérství',
        'description': 'Rychlé a spolehlivé instalatérské služby pro váš domov.',
        'services': [('Havarijní výjezd', 1800, 60), ('Oprava baterie', 950, 45), ('Montáž WC', 2400, 90), ('Revize rozvodů', 1500, 60)],
    },
    {
        'pk': 13, 'name': 'VOLT', 'kind': 'elektroinstalace',
        'description': 'Bezpečná elektroinstalace, revize a chytrá řešení.',
        'services': [('Revize elektro', 1800, 60), ('Zapojení spotřebiče', 750, 30), ('Výjezd elektrikáře', 950, 45), ('LED osvětlení', 1400, 60)],
    },
    {
        'pk': 14, 'name': 'Ateliér Domov', 'kind': 'rekonstrukce',
        'description': 'Proměňujeme bydlení v prostor, který vám bude sedět.',
        'services': [('Konzultace rekonstrukce', 1200, 60), ('Projekt', 4500, 90), ('Realizace koupelny', 3500, 90), ('Malířské práce', 950, 60)],
    },
    {
        'pk': 15, 'name': 'MotorBay', 'kind': 'autoservis',
        'description': 'Poctivý servis, přesná diagnostika a jistota na cestách.',
        'services': [('Servisní prohlídka', 1500, 60), ('Výměna oleje', 1200, 45), ('Diagnostika', 950, 45), ('Pneuservis', 1100, 45)],
    },
    {
        'pk': 16, 'name': 'RentGo', 'kind': 'půjčovna',
        'description': 'Vybavení a technika přesně tehdy, když je potřebujete.',
        'services': [('Pronájem nářadí / den', 490, 30), ('Vysokozdvižný vozík', 2200, 60), ('Přívěs', 750, 30), ('Generátor', 1250, 30)],
    },
    {
        'pk': 17, 'name': 'Ateliér 42', 'kind': 'fotografické studio',
        'description': 'Variabilní prostor pro fotografie, tvorbu i setkávání.',
        'services': [('Pronájem studia', 950, 60), ('Portrétní focení', 2400, 60), ('Produktové foto', 1900, 60), ('Workshop', 1200, 90)],
    },
]


class Command(BaseCommand):
    help = 'Vytvoří idempotentní data pro devět oborových ukázek (salony 9–17).'

    def handle(self, *args, **options):
        for demo in DEMOS:
            salon = Salon.objects.filter(pk=demo['pk']).first()
            if salon and salon.name != demo['name']:
                raise CommandError(
                    f"PK {demo['pk']} už patří salonu „{salon.name}“, nelze bezpečně vytvořit „{demo['name']}“."
                )

            if not salon:
                conflict = Salon.objects.filter(name=demo['name']).first()
                if conflict:
                    raise CommandError(
                        f"Salon „{demo['name']}“ už existuje pod PK {conflict.pk}; očekává se PK {demo['pk']}."
                    )
                salon = Salon(pk=demo['pk'], name=demo['name'])

            salon.description = demo['description']
            salon.address = f'Ukázková 42, Praha'
            salon.phone = f'+420 777 000 {demo["pk"]}'
            salon.email = f'info@{demo["name"].lower().replace(" ", "").replace("ě", "e").replace("í", "i")}.cz'
            salon.save()

            for index, (name, price, duration) in enumerate(demo['services']):
                CenikPolozka.objects.update_or_create(
                    salon=salon, nazev=name,
                    defaults={'cena': price, 'delka_minut': duration, 'rezerva_minut': 0, 'aktivni': True, 'poradi': index},
                )

            for title, text in [
                ('Online rezervace', f'Nově si u nás můžete snadno rezervovat termín online.'),
                ('Jsme tu pro vás', f'Objevte služby, které nabízí {demo["name"]}.'),
            ]:
                Novinka.objects.get_or_create(salon=salon, nadpis=title, defaults={'text': text})

            for day in range(7):
                open_day = day < 5
                OteviraciDoba.objects.update_or_create(
                    salon=salon, den=day,
                    defaults={'od': time(9, 0) if open_day else None, 'do': time(17, 0) if open_day else None, 'zavreno': not open_day},
                )

            RezervacniNastaveni.objects.update_or_create(
                salon=salon,
                defaults={
                    'interval_minut': 15, 'min_predstih_hodin': 2, 'max_predstih_mesicu': 3,
                    'storno_do_hodin': 24, 'email_odesilatel': salon.email,
                    'email_jmeno_odesilatele': salon.name, 'web_rezervace_url': '',
                },
            )

            owner, _ = Zamestnanec.objects.get_or_create(
                salon=salon, prihlasovaci_jmeno='majitelka',
                defaults={'jmeno': 'Majitelka', 'role': Zamestnanec.ROLE_MAJITEL, 'zobrazit_na_webu': False, 'aktivni': True},
            )
            owner.jmeno = 'Majitelka'
            owner.role = Zamestnanec.ROLE_MAJITEL
            owner.zobrazit_na_webu = False
            owner.aktivni = True
            owner.set_password('majitelka123')
            owner.save()

            worker, _ = Zamestnanec.objects.get_or_create(
                salon=salon, jmeno=f'Tým {demo["name"]}',
                defaults={'specializace': demo['kind'], 'popis': f'Pomůžeme vám s oborem: {demo["kind"]}.', 'zobrazit_na_webu': True, 'aktivni': True, 'poradi': 1},
            )
            worker.specializace = demo['kind']
            worker.zobrazit_na_webu = True
            worker.aktivni = True
            worker.save()
            for day in range(7):
                work_day = day < 5
                ZamestnanecRozvrh.objects.update_or_create(
                    zamestnanec=worker, den=day,
                    defaults={'od': time(9, 0) if work_day else None, 'do': time(17, 0) if work_day else None, 'volno': not work_day},
                )

            self.stdout.write(self.style.SUCCESS(f'{salon.pk}: {salon.name} připraven.'))
