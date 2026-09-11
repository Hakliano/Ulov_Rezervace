from datetime import time

from django.core.management.base import BaseCommand, CommandError

from django.db import connection

from partner_admin.models import PartnerNastaveni, vychozi_variabilni_symbol
from rezervace.models import RezervacniNastaveni, Zamestnanec, ZamestnanecRozvrh
from rezervace.services.booking_urls import DEMO_LIVE_BOOKING_URLS
from rezervace.services.staff_auth import ensure_owner_flow_user
from salons.management.commands.hulinek_services import hulinek_service_tuples
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
    {
        'pk': 20, 'name': 'Veterina Hulínek', 'kind': 'veterina',
        'email': 'info@veterinahulinek.cz',
        'owner_login': 'info@veterinahulinek.cz',
        'description': 'Pracujeme s vlastní laboratoří IDEXX, digitálním RTG a kompletní chirurgií. Ceny jednotlivých výkonů na webu neuvádíme — rádi je sdělíme při objednání nebo po telefonu.',
        'services': hulinek_service_tuples(),
    },
]


class Command(BaseCommand):
    help = 'Vytvoří idempotentní data pro oborové ukázky (salony 9–17 a 20).'

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
            elif demo['pk'] != 20 and CenikPolozka.objects.filter(salon=salon).exists():
                PartnerNastaveni.objects.filter(salon=salon).update(je_testovaci=True)
                self.stdout.write(f'{salon.pk}: {salon.name} existuje, obsah nechávám.')
                continue

            salon.description = demo['description']
            salon.address = demo.get('address') or 'Ukázková 42, Praha'
            salon.phone = demo.get('phone') or f'+420 777 000 {demo["pk"]}'
            slug = demo['name'].lower().replace(' ', '').replace('ě', 'e').replace('í', 'i').replace('á', 'a').replace('é', 'e').replace('ý', 'y').replace('ú', 'u').replace('ů', 'u').replace('č', 'c').replace('ř', 'r').replace('š', 's').replace('ž', 'z')
            salon.email = demo.get('email') or f'info@{slug}.cz'
            salon.save()
            partner, _ = PartnerNastaveni.objects.get_or_create(
                salon=salon,
                defaults={
                    'fakturacni_email': salon.email,
                    'je_testovaci': True,
                    'variabilni_symbol': vychozi_variabilni_symbol(salon.pk) or None,
                },
            )
            if not partner.je_testovaci:
                partner.je_testovaci = True
                partner.save(update_fields=['je_testovaci'])

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

            nast_defaults = {
                'interval_minut': 15, 'min_predstih_hodin': 2, 'max_predstih_mesicu': 3,
                'storno_do_hodin': 24, 'email_odesilatel': salon.email,
                'email_jmeno_odesilatele': salon.name,
            }
            # web_rezervace_url NIKDY nepřepisovat na prázdno — maže LIVE odkazy v e-mailech
            nast, created = RezervacniNastaveni.objects.get_or_create(
                salon=salon, defaults={
                    **nast_defaults,
                    'web_rezervace_url': DEMO_LIVE_BOOKING_URLS.get(salon.pk, ''),
                },
            )
            if not created:
                for key, val in nast_defaults.items():
                    setattr(nast, key, val)
                raw = (nast.web_rezervace_url or '').strip()
                if (not raw) or ('localhost' in raw.lower()):
                    mapped = DEMO_LIVE_BOOKING_URLS.get(salon.pk, '')
                    if mapped:
                        nast.web_rezervace_url = mapped
                nast.save()

            owner_login = demo.get('owner_login') or f'majitel.salon{salon.pk}@ulov.local'
            owner, created = Zamestnanec.objects.get_or_create(
                salon=salon, role=Zamestnanec.ROLE_MAJITEL,
                defaults={
                    'jmeno': 'Majitelka',
                    'prihlasovaci_jmeno': owner_login,
                    'zobrazit_na_webu': False,
                    'aktivni': True,
                },
            )
            if created or not owner.prihlasovaci_jmeno or '@' not in owner.prihlasovaci_jmeno:
                owner.prihlasovaci_jmeno = owner_login
            owner.jmeno = 'Majitelka'
            owner.role = Zamestnanec.ROLE_MAJITEL
            owner.zobrazit_na_webu = False
            owner.aktivni = True
            owner.set_password('majitelka123')
            owner.save()
            try:
                ensure_owner_flow_user(salon, email=owner.prihlasovaci_jmeno)
            except ValueError as exc:
                self.stdout.write(self.style.WARNING(f'{salon.pk}: FLOW účet: {exc}'))

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

        if connection.vendor == 'postgresql':
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT setval(pg_get_serial_sequence('salons_salon','id'),"
                    " (SELECT MAX(id) FROM salons_salon))"
                )
