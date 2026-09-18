"""P6.0 showcase kartotéka pro existující salon 10 – PawCare.

Nepřidává nového partnera. Nemění web, FLOW, personál ani ceník.
Standardní P3 vet preset. Žádné fotografie ani PDF.
Bez --reset nikdy nemaže kartotéku (ochrana ručně nahraných souborů).
Nespouštět na LIVE.
"""
from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from archivnik.models import (
    Asset,
    CustomFieldDef,
    CustomFieldValue,
    Customer,
    Entry,
    Obor,
    Object,
    ObjectType,
    Reminder,
    ReminderStav,
)
from archivnik.services import apply_preset
from rezervace.models import Zamestnanec
from salons.models import Salon

TZ = ZoneInfo('Europe/Prague')

DEFAULT_SALON_ID = 10
EXPECTED_NAME = 'PawCare'
EMAIL_DOMAIN = 'demo.local'


class PawCareShowcaseError(Exception):
    pass


def _at(d: date, hour=10, minute=0) -> datetime:
    return datetime(d.year, d.month, d.day, hour, minute, tzinfo=TZ)


def _stamp(instance, created: datetime, updated: datetime | None = None):
    fields = {}
    model = instance.__class__
    names = {f.name for f in model._meta.fields}
    if 'vytvoreno' in names:
        fields['vytvoreno'] = created
    if 'upraveno' in names:
        fields['upraveno'] = updated or created
    if fields:
        model.objects.filter(pk=instance.pk).update(**fields)


def _field_map(typ: ObjectType) -> dict[str, CustomFieldDef]:
    return {p.nazev: p for p in CustomFieldDef.objects.filter(typ=typ, aktivni=True)}


def _set_fields(obj: Object, values: dict[str, str], fmap: dict[str, CustomFieldDef]):
    for nazev, hodnota in values.items():
        pole = fmap.get(nazev)
        if pole is None or hodnota in (None, ''):
            continue
        CustomFieldValue.objects.update_or_create(
            objekt=obj, pole=pole, defaults={'hodnota': str(hodnota)},
        )


def _wipe_kartoteka(salon):
    """Jen kartotéka tohoto salonu. Web, FLOW, personál, ceník, Obor i typy zůstanou."""
    Object.objects.filter(salon=salon).update(cover=None)
    Asset.objects.filter(salon=salon).delete()
    CustomFieldValue.objects.filter(objekt__salon=salon).delete()
    Entry.objects.filter(salon=salon).delete()
    Reminder.objects.filter(salon=salon).delete()
    Object.objects.filter(salon=salon).delete()
    Customer.objects.filter(salon=salon).delete()


def counts(salon) -> dict:
    reminders = Reminder.objects.filter(salon=salon)
    entries = Entry.objects.filter(salon=salon)
    customers = Customer.objects.filter(salon=salon)
    objects = Object.objects.filter(salon=salon)
    dates = []
    dates += list(customers.values_list('vytvoreno', flat=True))
    dates += list(objects.values_list('vytvoreno', flat=True))
    dates += list(entries.values_list('nastalo', flat=True))
    dates += list(reminders.values_list('termin', flat=True))
    aware = []
    for item in dates:
        if item is None:
            continue
        if isinstance(item, date) and not isinstance(item, datetime):
            aware.append(datetime.combine(item, time.min, tzinfo=TZ))
        else:
            aware.append(item)
    return {
        'zakaznici': customers.count(),
        'objekty': objects.count(),
        'zapisy': entries.count(),
        'pripominky': reminders.count(),
        'pripominky_aktivni': reminders.filter(stav=ReminderStav.AKTIVNI).count(),
        'pripominky_hotovo': reminders.filter(stav=ReminderStav.HOTOVO).count(),
        'soubory': Asset.objects.filter(salon=salon).count(),
        'obor_preset': list(
            Obor.objects.filter(salon=salon).values_list('nazev', 'zdroj_preset')
        ),
        'historie_od': min(aware).isoformat() if aware else None,
        'historie_do': max(aware).isoformat() if aware else None,
    }


def showcase_cards(salon) -> list[dict]:
    wanted = [
        ('Lucie', 'Dvořáková'),
        ('Martin', 'Jelínek'),
        ('Petra', 'Šimková'),
        ('Tomáš', 'Beneš'),
    ]
    rows = []
    for jmeno, prijmeni in wanted:
        c = Customer.objects.filter(salon=salon, jmeno=jmeno, prijmeni=prijmeni).first()
        if not c:
            continue
        objekty = [
            {'nazev': o.nazev, 'typ': o.typ.nazev}
            for o in Object.objects.filter(zakaznik=c).select_related('typ')
        ]
        rows.append({
            'display_name': c.display_name,
            'email': c.email,
            'objekty': objekty,
            'zapisy': Entry.objects.filter(zakaznik=c).count(),
            'pripominky': Reminder.objects.filter(zakaznik=c).count(),
        })
    return rows


def dataset():
    """Fiktivní karty. Klíče objektů jsou názvy zvířat."""
    return [
        {
            'jmeno': 'Lucie', 'prijmeni': 'Dvořáková',
            'email': f'lucie.dvorakova@{EMAIL_DOMAIN}',
            'telefon': '770 010 101',
            'adresa': 'Komenského 14, Brandýs nad Labem',
            'poznamka': 'Chodí pravidelně, preferuje SMS. Max je citlivý na pravé ucho.',
            'created': date(2026, 1, 14),
            'objects': [
                {
                    'nazev': 'Max', 'typ': 'Pes',
                    'created': date(2026, 1, 14),
                    'popis': 'Klidný rodinný pes, zvyklý na ošetření.',
                    'fields': {
                        'Plemeno': 'Labrador retriever',
                        'Pohlaví': 'Samec',
                        'Datum narození': '2018-04-12',
                        'Barva / zbarvení': 'žlutá',
                        'Číslo čipu': '203098110000101',
                        'Číslo pasu': 'CZ 11 0101',
                        'Hmotnost': '32.4',
                        'Kastrace': 'ne',
                        'Alergie / upozornění': 'Citlivé pravé ucho. Nesnáší agresivní čisticí roztoky.',
                    },
                },
            ],
            'entries': [
                ('2026-01-14', 9, None, 'Kontakt', 'Komunikace',
                 'Preferuje SMS. E-mail jen na kopii nálezů.'),
                ('2026-01-14', 10, 'Max', 'Prohlídka', 'Preventivní prohlídka',
                 'Vstupní prohlídka. Kondice dobrá, mírný nadváha. Doporučena kontrola krmné dávky.'),
                ('2026-01-14', 11, 'Max', 'Očkování', 'Pravidelné očkování',
                 'Kombinovaná vakcína + vzteklina. Bez reakce po aplikaci.'),
                ('2026-03-10', 9, 'Max', 'Ošetření', 'Kontrola pravého ucha',
                 'Mírný zánět zevního zvukovodu vpravo. Výplach, kapky 7 dní, kontrola za 10 dní.'),
                ('2026-03-20', 10, 'Max', 'Kontrola', 'Kontrola po léčbě',
                 'Ucho klidné, výtok ustoupil. Pokračovat v šetrném čištění 1× týdně.'),
                ('2026-05-06', 9, 'Max', 'Prohlídka', 'Kontrola hmotnosti',
                 '31,8 kg. Mírný pokles, držet současnou dávku. Pohyb denně 45 minut.'),
                ('2026-07-22', 10, 'Max', 'Prohlídka', 'Kontrola chrupu',
                 'Mírný zubní kámen na P4. Zatím bez zákroku, doporučen dentální žvýkací pamlsek.'),
                ('2026-08-14', 9, 'Max', 'Konzultace', 'Konzultace krmení',
                 'Řešena krmná dávka po dovolené. Vrátit se k původnímu granulátu, bez zbytků ze stolu.'),
                ('2026-09-08', 10, 'Max', 'Ošetření', 'Kontrola pravého ucha',
                 'Občasné kytí po koupání. Preventivní výplach, bez zánětu.'),
            ],
            'reminders': [
                ('2026-01-14', 'Max', 'Přeočkování Maxe — jaro', ReminderStav.HOTOVO),
                ('2026-10-12', 'Max', 'Pravidelné očkování — Max', ReminderStav.AKTIVNI),
                ('2026-11-04', 'Max', 'Kontrola hmotnosti — Max', ReminderStav.AKTIVNI),
            ],
        },
        {
            'jmeno': 'Martin', 'prijmeni': 'Jelínek',
            'email': f'martin.jelinek@{EMAIL_DOMAIN}',
            'telefon': '770 010 102',
            'adresa': 'Husova 7, Čelákovice',
            'poznamka': 'Bella je první. Charlie přišel v dubnu z útulku. Jezdí oba najednou, když to jde.',
            'created': date(2026, 2, 3),
            'objects': [
                {
                    'nazev': 'Bella', 'typ': 'Kočka',
                    'created': date(2026, 2, 3),
                    'popis': 'Bytová kočka, zvyklá na přepravku.',
                    'fields': {
                        'Plemeno': 'Evropská krátkosrstá',
                        'Pohlaví': 'Samice',
                        'Datum narození': '2021-06-02',
                        'Barva / zbarvení': 'želvovinová',
                        'Číslo čipu': '203098110000102',
                        'Hmotnost': '4.1',
                        'Kastrace': 'ano',
                    },
                },
                {
                    'nazev': 'Charlie', 'typ': 'Pes',
                    'created': date(2026, 4, 11),
                    'popis': 'Střední kříženec z útulku, stále se zklidňuje.',
                    'fields': {
                        'Plemeno': 'kříženec (střední)',
                        'Pohlaví': 'Samec',
                        'Datum narození': '2023-09-20',
                        'Barva / zbarvení': 'černá s pálením',
                        'Číslo čipu': '203098110000103',
                        'Hmotnost': '18.6',
                        'Kastrace': 'ano',
                        'Alergie / upozornění': 'Nejistý u cizích psů. Objednávat mimo špičku v čekárně.',
                    },
                },
            ],
            'entries': [
                ('2026-02-03', 10, 'Bella', 'Prohlídka', 'Preventivní prohlídka',
                 'Roční prohlídka. Kastrovaná, kondice v normě. Doporučeno dentální ošetření na podzim.'),
                ('2026-02-03', 11, 'Bella', 'Očkování', 'Pravidelné očkování',
                 'Přeočkování kočičí kombinace. Bez komplikací.'),
                ('2026-04-11', 10, 'Charlie', 'Prohlídka', 'Vstupní prohlídka',
                 'Nově z útulku. Čip ověřen, kastrovaný. Mírný zánět ucha vlevo, zahájena léčba.'),
                ('2026-04-11', 11, 'Charlie', 'Očkování', 'Pravidelné očkování',
                 'Doplněna vzteklina podle útulkového průkazu. Harmonogram vysvětlen majiteli.'),
                ('2026-04-22', 9, 'Charlie', 'Kontrola', 'Kontrola po léčbě',
                 'Levé ucho klidné. Charlie se v čekárně zklidnil s Bella v přepravce.'),
                ('2026-06-20', 10, 'Bella', 'Ošetření', 'Kontrola kůže',
                 'Občasné škrábání za ušima. Bez parazitů, doporučen hypoalergenní šampon.'),
                ('2026-07-15', 9, 'Charlie', 'Prohlídka', 'Kontrola hmotnosti',
                 '18,6 kg. Držet současnou dávku, nepřikrmovat zbytky.'),
                ('2026-09-10', 10, 'Bella', 'Prohlídka', 'Kontrola chrupu',
                 'Zubní kámen na trhákech. Objednat dentální ošetření na listopad.'),
            ],
            'reminders': [
                ('2026-02-03', 'Bella', 'Přeočkování Belly', ReminderStav.HOTOVO),
                ('2026-10-20', 'Charlie', 'Přeočkování Charlieho', ReminderStav.AKTIVNI),
                ('2026-11-18', 'Bella', 'Dentální ošetření — Bella', ReminderStav.AKTIVNI),
            ],
        },
        {
            'jmeno': 'Petra', 'prijmeni': 'Šimková',
            'email': f'petra.simkova@{EMAIL_DOMAIN}',
            'telefon': '770 010 103',
            'adresa': 'Zahradní 3, Lysá nad Labem',
            'poznamka': 'Králík Písek žije v bytě. Majitelka dbá na seno ad libitum.',
            'created': date(2026, 3, 5),
            'objects': [
                {
                    'nazev': 'Písek', 'typ': 'Králík',
                    'created': date(2026, 3, 5),
                    'popis': 'Zakrslý beran, zvyklý na vyšetření na stole.',
                    'fields': {
                        'Plemeno': 'Zakrslý beran',
                        'Pohlaví': 'Samec',
                        'Datum narození': '2024-01-18',
                        'Barva': 'písková',
                        'Hmotnost': '1.7',
                        'Číslo čipu': '203098110000104',
                        'Kastrace': 'ano',
                        'Alergie / upozornění': 'Nesmí granule s obilovinami. Pouze seno a bylinková směs.',
                    },
                },
            ],
            'entries': [
                ('2026-03-05', 10, 'Písek', 'Prohlídka', 'Preventivní prohlídka',
                 'Vstupní prohlídka. Kastrovaný, krunýř zubů v normě. Vysvětleno krmení senem.'),
                ('2026-03-05', 11, 'Písek', 'Ošetření', 'Kontrola chrupu',
                 'Řezáky rovné, stoličky bez hrotů. Kontrola za 4 měsíce.'),
                ('2026-05-19', 9, 'Písek', 'Očkování', 'Pravidelné očkování',
                 'Myxomatóza / mor. Bez reakce. Další dávka na podzim.'),
                ('2026-07-02', 10, 'Písek', 'Prohlídka', 'Kontrola hmotnosti',
                 '1,72 kg. Stabilní. Stoličky v pořádku.'),
                ('2026-08-21', 9, 'Písek', 'Ošetření', 'Kontrola chrupu',
                 'Mírně prodloužené stoličky vlevo. Úprava, kontrola za 6 týdnů.'),
                ('2026-09-04', 11, 'Písek', 'Konzultace', 'Konzultace krmení',
                 'Po úpravě zubů přidat více lučního sena, omezit pamlsky.'),
            ],
            'reminders': [
                ('2026-05-19', 'Písek', 'Očkování Píska — jaro', ReminderStav.HOTOVO),
                ('2026-10-02', 'Písek', 'Kontrola chrupu — Písek', ReminderStav.AKTIVNI),
                ('2026-11-05', 'Písek', 'Podzimní očkování — Písek', ReminderStav.AKTIVNI),
            ],
        },
        {
            'jmeno': 'Tomáš', 'prijmeni': 'Beneš',
            'email': f'tomas.benes@{EMAIL_DOMAIN}',
            'telefon': '770 010 104',
            'adresa': 'Nádražní 22, Brandýs nad Labem',
            'poznamka': 'Papoušek Kiki. Objednávat jako první ranní termín, méně hluku v čekárně.',
            'created': date(2026, 2, 18),
            'objects': [
                {
                    'nazev': 'Kiki', 'typ': 'Pták / papoušek',
                    'created': date(2026, 2, 18),
                    'popis': 'Andulka, samičí, zvyklá na ruce.',
                    'fields': {
                        'Druh': 'Andulka vlnkovaná',
                        'Pohlaví': 'Samice',
                        'Datum narození / vylíhnutí': '2023-11-08',
                        'Zbarvení': 'modrá, bílá čepička',
                        'Identifikační kroužek': 'CZ 2023 44821',
                        'Hmotnost': '32',
                        'Alergie / upozornění': 'Nesnáší Teflon / přehřáté pánve v domácnosti. Připomenuto majiteli.',
                    },
                },
            ],
            'entries': [
                ('2026-02-18', 8, 'Kiki', 'Prohlídka', 'Preventivní prohlídka',
                 'Vstupní prohlídka. Opeření kvalitní, zobák i drápky mírně přerostlé. Úprava dnes.'),
                ('2026-02-18', 9, 'Kiki', 'Ošetření', 'Stříhání drápků',
                 'Drápky a mírná úprava zobáku. Bez krvácení. Kiki v klidu na ručníku.'),
                ('2026-04-09', 10, 'Kiki', 'Prohlídka', 'Kontrola hmotnosti',
                 '32 g. Stabilní. Trus formovaný, bez příměsi.'),
                ('2026-06-11', 9, 'Kiki', 'Konzultace', 'Konzultace krmení',
                 'Řešen podíl zrna versus granulát. Doporučen extrudovaný granulát jako základ.'),
                ('2026-07-30', 11, 'Kiki', 'Ošetření', 'Stříhání drápků',
                 'Drápky upraveny. Opeření v pořádku, bez výletů z klece v ordinaci.'),
                ('2026-09-02', 10, 'Kiki', 'Prohlídka', 'Preventivní prohlídka',
                 'Kontrola před podzimem. Hmotnost 31 g. Bez nálezu na kůži ani zobáku.'),
            ],
            'reminders': [
                ('2026-10-08', 'Kiki', 'Stříhání drápků — Kiki', ReminderStav.AKTIVNI),
            ],
        },
        {
            'jmeno': 'Jana', 'prijmeni': 'Novotná',
            'email': f'jana.novotna@{EMAIL_DOMAIN}',
            'telefon': '770 010 105',
            'adresa': 'Palackého 9, Nymburk',
            'poznamka': 'Pes i kočka. Kočku vozí zvlášť.',
            'created': date(2026, 1, 28),
            'objects': [
                {
                    'nazev': 'Rex', 'typ': 'Pes',
                    'created': date(2026, 1, 28),
                    'fields': {
                        'Plemeno': 'Německý ovčák',
                        'Pohlaví': 'Samec',
                        'Datum narození': '2019-02-01',
                        'Číslo čipu': '203098110000105',
                        'Hmotnost': '36.0',
                        'Kastrace': 'ne',
                    },
                },
                {
                    'nazev': 'Lili', 'typ': 'Kočka',
                    'created': date(2026, 2, 12),
                    'fields': {
                        'Plemeno': 'Britská krátkosrstá',
                        'Pohlaví': 'Samice',
                        'Kastrace': 'ano',
                        'Hmotnost': '4.8',
                    },
                },
            ],
            'entries': [
                ('2026-01-28', 10, 'Rex', 'Prohlídka', 'Preventivní prohlídka',
                 'Roční prohlídka. Pohybový aparát v pořádku, doporučeno nepřetěžovat klouby v terénu.'),
                ('2026-01-28', 11, 'Rex', 'Očkování', 'Pravidelné očkování',
                 'Kombinace + vzteklina. Bez reakce.'),
                ('2026-02-12', 9, 'Lili', 'Prohlídka', 'Preventivní prohlídka',
                 'První návštěva kočky. Kastrovaná, čip nemá — nabídnut, zatím odloženo.'),
                ('2026-08-19', 9, 'Lili', 'Očkování', 'Pravidelné očkování',
                 'Přeočkování. Lili ve stresu, vyšetření zkráceno.'),
            ],
            'reminders': [
                ('2026-06-01', 'Rex', 'Kontrola drápků — Rex', ReminderStav.HOTOVO),
            ],
        },
        {
            'jmeno': 'Ondřej', 'prijmeni': 'Kratochvíl',
            'email': f'ondrej.kratochvil@{EMAIL_DOMAIN}',
            'telefon': '770 010 106',
            'adresa': 'Hlavní 41, Stránčice',
            'created': date(2026, 3, 18),
            'objects': [
                {
                    'nazev': 'Mína', 'typ': 'Kočka',
                    'created': date(2026, 3, 18),
                    'fields': {
                        'Plemeno': 'Siamská',
                        'Pohlaví': 'Samice',
                        'Datum narození': '2022-03-14',
                        'Kastrace': 'ano',
                        'Hmotnost': '3.6',
                    },
                },
                {
                    'nazev': 'Gusto', 'typ': 'Kočka',
                    'created': date(2026, 3, 18),
                    'fields': {
                        'Pohlaví': 'Samec',
                        'Kastrace': 'ano',
                        'Barva / zbarvení': 'černá',
                    },
                },
            ],
            'entries': [
                ('2026-03-18', 10, 'Mína', 'Prohlídka', 'Preventivní prohlídka',
                 'Obě kočky v jedné domácnosti. Mína v pořádku, doporučeno odčervení.'),
                ('2026-03-18', 11, 'Gusto', 'Prohlídka', 'Preventivní prohlídka',
                 'Gusto mírně nadváha. Snížit pamlsky, krmit odměřeně.'),
                ('2026-07-08', 9, 'Mína', 'Očkování', 'Pravidelné očkování',
                 'Přeočkování. Gusto dnes nebyl — objednat zvlášť.'),
            ],
            'reminders': [],
        },
        {
            'jmeno': 'Eva', 'prijmeni': 'Horáková',
            'email': f'eva.horakova@{EMAIL_DOMAIN}',
            'telefon': '770 010 107',
            'created': date(2026, 5, 21),
            'objects': [
                {
                    'nazev': 'Fík', 'typ': 'Morče',
                    'created': date(2026, 5, 21),
                    'fields': {
                        'Plemeno': 'Americké morče',
                        'Pohlaví': 'Samec',
                        'Hmotnost': '0.95',
                    },
                },
            ],
            'entries': [
                ('2026-05-21', 15, 'Fík', 'Prohlídka', 'Preventivní prohlídka',
                 'Nové morče. Zuby v normě, doporučeno seno a vitamin C v zelenině.'),
                ('2026-08-06', 10, 'Fík', 'Ošetření', 'Kontrola chrupu',
                 'Řezáky rovné. Hmotnost stabilní.'),
            ],
            'reminders': [],
        },
        {
            'jmeno': 'Barbora', 'prijmeni': 'Malá',
            'email': f'barbora.mala@{EMAIL_DOMAIN}',
            'telefon': '770 010 108',
            'adresa': 'Školní 5, Úvaly',
            'poznamka': 'Ares je aktivní, objednávat delší slot.',
            'created': date(2026, 2, 25),
            'objects': [
                {
                    'nazev': 'Ares', 'typ': 'Pes',
                    'created': date(2026, 2, 25),
                    'fields': {
                        'Plemeno': 'Border kolie',
                        'Pohlaví': 'Samec',
                        'Datum narození': '2022-08-30',
                        'Číslo čipu': '203098110000108',
                        'Hmotnost': '17.2',
                        'Kastrace': 'ne',
                    },
                },
            ],
            'entries': [
                ('2026-02-25', 10, 'Ares', 'Prohlídka', 'Preventivní prohlídka',
                 'Sportovní pes. Pohybový aparát bez nálezu, doporučena kloubní výživa v zátěži.'),
                ('2026-04-16', 9, 'Ares', 'Očkování', 'Pravidelné očkování',
                 'Přeočkování. Bez reakce.'),
                ('2026-07-09', 8, 'Ares', 'Ošetření', 'Ošetření drobného poranění',
                 'Odřenina na běhu po tréninku. Očištění, sprej, klid 5 dní.'),
            ],
            'reminders': [
                ('2026-09-25', 'Ares', 'Kontrola pohybového aparátu — Ares', ReminderStav.AKTIVNI),
            ],
        },
        {
            'jmeno': 'Pavel', 'prijmeni': 'Černý',
            'email': f'pavel.cerny@{EMAIL_DOMAIN}',
            'telefon': '770 010 109',
            'created': date(2026, 8, 22),
            'objects': [
                {
                    'nazev': 'Hedvika', 'typ': 'Kočka',
                    'created': date(2026, 8, 22),
                    'fields': {
                        'Pohlaví': 'Samice',
                        'Barva / zbarvení': 'šedá',
                        'Kastrace': 'ne',
                    },
                },
            ],
            'entries': [
                ('2026-08-22', 16, 'Hedvika', 'Prohlídka', 'Preventivní prohlídka',
                 'Nová klientka. Kočka z venkovního chovu, zatím bez čipu. Nabídnuto čipování příště.'),
                ('2026-09-05', 10, 'Hedvika', 'Ošetření', 'Kontrola kůže',
                 'Mírné škrábance na krku. Lokální ošetření, bez celkových léků.'),
            ],
            'reminders': [],
        },
        {
            'jmeno': 'Klára', 'prijmeni': 'Veselá',
            'email': f'klara.vesela@{EMAIL_DOMAIN}',
            'telefon': '770 010 110',
            'adresa': 'Polní 11, Nehvizdy',
            'poznamka': 'Tři drobná zvířata. Objednává odpoledne po škole.',
            'created': date(2026, 4, 2),
            'objects': [
                {
                    'nazev': 'Ušák', 'typ': 'Králík',
                    'created': date(2026, 4, 2),
                    'fields': {
                        'Plemeno': 'Český albín',
                        'Pohlaví': 'Samec',
                        'Hmotnost': '3.8',
                        'Kastrace': 'ano',
                    },
                },
                {
                    'nazev': 'Nouma', 'typ': 'Morče',
                    'created': date(2026, 4, 2),
                    'fields': {
                        'Pohlaví': 'Samice',
                        'Barva': 'tříbarevná',
                    },
                },
                {
                    'nazev': 'Píďa', 'typ': 'Křeček',
                    'created': date(2026, 6, 16),
                    'fields': {
                        'Druh / plemeno': 'Křeček zlatý',
                        'Pohlaví': 'Samec',
                    },
                },
            ],
            'entries': [
                ('2026-04-02', 14, 'Ušák', 'Prohlídka', 'Preventivní prohlídka',
                 'Králík i morče přivezeny spolu. Ušák kastrovaný, zuby v normě.'),
                ('2026-04-02', 15, 'Nouma', 'Prohlídka', 'Preventivní prohlídka',
                 'Morče bez nálezu. Doporučen vitamin C v paprice.'),
                ('2026-06-16', 10, 'Píďa', 'Prohlídka', 'Preventivní prohlídka',
                 'Nový křeček. Kůže v pořádku, poučena o nočním režimu a kleci.'),
                ('2026-08-13', 9, 'Ušák', 'Ošetření', 'Kontrola chrupu',
                 'Stoličky v pořádku. Hmotnost mírně nahoru — omezit granule.'),
            ],
            'reminders': [
                ('2026-10-28', 'Ušák', 'Kontrola chrupu — Ušák', ReminderStav.AKTIVNI),
            ],
        },
        {
            'jmeno': 'Adam', 'prijmeni': 'Procházka',
            'email': f'adam.prochazka@{EMAIL_DOMAIN}',
            'telefon': '770 010 111',
            'adresa': 'Jiráskova 8, Brandýs nad Labem',
            'created': date(2026, 1, 9),
            'objects': [
                {
                    'nazev': 'Rocky', 'typ': 'Pes',
                    'created': date(2026, 1, 9),
                    'fields': {
                        'Plemeno': 'Golden retriever',
                        'Pohlaví': 'Samec',
                        'Datum narození': '2020-11-03',
                        'Číslo čipu': '203098110000111',
                        'Číslo pasu': 'CZ 11 0111',
                        'Hmotnost': '34.1',
                        'Kastrace': 'ano',
                    },
                },
                {
                    'nazev': 'Bára', 'typ': 'Pes',
                    'created': date(2026, 6, 4),
                    'fields': {
                        'Plemeno': 'Jorkšírský teriér',
                        'Pohlaví': 'Samice',
                        'Hmotnost': '3.2',
                        'Kastrace': 'ano',
                    },
                },
            ],
            'entries': [
                ('2026-01-09', 10, 'Rocky', 'Očkování', 'Pravidelné očkování',
                 'Roční přeočkování. Rocky v pořádku, doporučena kontrola kyčlí při další návštěvě.'),
                ('2026-04-23', 9, 'Rocky', 'Prohlídka', 'Kontrola hmotnosti',
                 '34,1 kg. Držet dávku, po zimě méně pohybu — přidat delší vycházky.'),
                ('2026-06-04', 11, 'Bára', 'Prohlídka', 'Preventivní prohlídka',
                 'Nová fena v domácnosti. Kastrovaná, očkovací průkaz doplněn.'),
            ],
            'reminders': [],
        },
        {
            'jmeno': 'Tereza', 'prijmeni': 'Pokorná',
            'email': f'tereza.pokorna@{EMAIL_DOMAIN}',
            'telefon': '770 010 112',
            'created': date(2026, 6, 25),
            'objects': [
                {
                    'nazev': 'Coco', 'typ': 'Pták / papoušek',
                    'created': date(2026, 6, 25),
                    'fields': {
                        'Druh': 'Korela chocholatá',
                        'Pohlaví': 'Neurčeno',
                        'Zbarvení': 'lutino',
                    },
                },
            ],
            'entries': [
                ('2026-06-25', 13, 'Coco', 'Prohlídka', 'Preventivní prohlídka',
                 'Nový pták. Zobák v pořádku, doporučena větší klec a sepiová kost.'),
                ('2026-09-01', 10, 'Coco', 'Ošetření', 'Stříhání drápků',
                 'Drápky upraveny. Hmotnost odhadem v normě — příště zvážit.'),
            ],
            'reminders': [],
        },
        {
            'jmeno': 'Michal', 'prijmeni': 'Svoboda',
            'email': f'michal.svoboda@{EMAIL_DOMAIN}',
            'telefon': '770 010 113',
            'adresa': 'U Potoka 2, Lázně Toušeň',
            'created': date(2026, 5, 7),
            'objects': [
                {
                    'nazev': 'Dunka', 'typ': 'Fretka',
                    'created': date(2026, 5, 7),
                    'fields': {
                        'Pohlaví': 'Samice',
                        'Datum narození': '2024-08-01',
                        'Barva': 'sable',
                        'Číslo čipu': '203098110000113',
                        'Hmotnost': '0.82',
                        'Kastrace': 'ano',
                    },
                },
            ],
            'entries': [
                ('2026-05-07', 10, 'Dunka', 'Prohlídka', 'Preventivní prohlídka',
                 'Fretka kastrovaná, čip ověřen. Kůže v pořádku, očkování odloženo na podzim.'),
                ('2026-07-16', 9, 'Dunka', 'Ošetření', 'Kontrola uší',
                 'Obě uši čisté. Doporučeno pravidelné čištění 1× měsíčně.'),
            ],
            'reminders': [
                ('2026-09-30', 'Dunka', 'Podzimní očkování — Dunka', ReminderStav.AKTIVNI),
            ],
        },
        {
            'jmeno': 'Ivana', 'prijmeni': 'Kučerová',
            'email': f'ivana.kucerova@{EMAIL_DOMAIN}',
            'telefon': '770 010 114',
            'created': date(2026, 9, 8),
            'objects': [
                {
                    'nazev': 'Punťa', 'typ': 'Pes',
                    'created': date(2026, 9, 8),
                    'fields': {
                        'Plemeno': 'kříženec (malý)',
                        'Pohlaví': 'Samec',
                        'Datum narození': '2026-07-01',
                        'Hmotnost': '4.3',
                        'Kastrace': 'ne',
                    },
                },
            ],
            'entries': [
                ('2026-09-08', 10, 'Punťa', 'Prohlídka', 'Preventivní prohlídka',
                 'Štěně, první návštěva. Odčervení, vysvětlen harmonogram vakcinace. Průkaz přinesou příště.'),
                ('2026-09-08', 11, 'Punťa', 'Očkování', 'Pravidelné očkování',
                 'První dávka kombinované vakcíny. Bez reakce v ordinaci, pozorovat 24 hodin.'),
            ],
            'reminders': [
                ('2026-10-02', 'Punťa', 'Druhé očkování — Punťa', ReminderStav.AKTIVNI),
            ],
        },
        {
            'jmeno': 'Alena', 'prijmeni': 'Němcová',
            'email': f'alena.nemcova@{EMAIL_DOMAIN}',
            'telefon': '770 010 115',
            'adresa': 'Sadová 16, Nymburk',
            'poznamka': 'Pes senior a kočka. Jezdí ráno.',
            'created': date(2026, 1, 21),
            'objects': [
                {
                    'nazev': 'Gump', 'typ': 'Pes',
                    'created': date(2026, 1, 21),
                    'fields': {
                        'Plemeno': 'kříženec (velký)',
                        'Pohlaví': 'Samec',
                        'Datum narození': '2014-05-09',
                        'Číslo čipu': '203098110000115',
                        'Hmotnost': '28.7',
                        'Kastrace': 'ano',
                        'Alergie / upozornění': 'Senior. Při odběru krve plánovat delší termín.',
                    },
                },
                {
                    'nazev': 'Žofie', 'typ': 'Kočka',
                    'created': date(2026, 1, 21),
                    'fields': {
                        'Pohlaví': 'Samice',
                        'Kastrace': 'ano',
                        'Barva / zbarvení': 'bílá s šedými znaky',
                        'Hmotnost': '4.0',
                    },
                },
            ],
            'entries': [
                ('2026-01-21', 9, 'Gump', 'Prohlídka', 'Preventivní prohlídka',
                 'Senior. Mírný šelest, zatím bez léků. Doporučena kontrola krve na jaře.'),
                ('2026-01-21', 10, 'Žofie', 'Očkování', 'Pravidelné očkování',
                 'Přeočkování. Kočka v pořádku.'),
                ('2026-04-08', 8, 'Gump', 'Laboratoř', 'Odběr krve',
                 'Biochemie a krevní obraz. Výsledky zavolat po obědě.'),
                ('2026-04-09', 14, 'Gump', 'Laboratoř', 'Výsledky laboratorního vyšetření',
                 'Mírně zvýšená urea, ostatní v normě. Kontrola za 6 měsíců, dostatek vody.'),
            ],
            'reminders': [
                ('2026-12-03', 'Gump', 'Kontrolní odběr krve — Gump', ReminderStav.AKTIVNI),
            ],
        },
    ]


def _load_salon(salon_id: int):
    salon = Salon.objects.filter(pk=salon_id).first()
    if salon is None:
        raise PawCareShowcaseError(f'Salon {salon_id} neexistuje.')
    if salon.name != EXPECTED_NAME:
        raise PawCareShowcaseError(
            f'Salon {salon_id} se jmenuje „{salon.name}“, očekává se „{EXPECTED_NAME}“. '
            'Nový tenant se nezakládá.'
        )
    owner = (
        Zamestnanec.objects.filter(salon=salon, role=Zamestnanec.ROLE_MAJITEL)
        .order_by('id')
        .first()
    )
    if owner is None:
        raise PawCareShowcaseError(f'Salon {salon_id} nemá majitele.')
    return salon, owner


def _seed_rows(salon, owner):
    types = {t.nazev: t for t in ObjectType.objects.filter(salon=salon, aktivni=True)}
    field_maps = {nazev: _field_map(typ) for nazev, typ in types.items()}

    for spec in dataset():
        created = _at(spec['created'], 8, 30)
        customer = Customer.objects.create(
            salon=salon,
            jmeno=spec['jmeno'],
            prijmeni=spec['prijmeni'],
            email=spec.get('email') or '',
            telefon=spec.get('telefon') or '',
            adresa=spec.get('adresa') or '',
            poznamka=spec.get('poznamka') or '',
            vytvoril=owner,
            zmenil=owner,
        )
        _stamp(customer, created)

        objects = {}
        for obj_spec in spec['objects']:
            typ = types[obj_spec['typ']]
            obj_created = _at(obj_spec['created'], 9, 0)
            obj = Object.objects.create(
                salon=salon,
                zakaznik=customer,
                typ=typ,
                nazev=obj_spec['nazev'],
                popis=obj_spec.get('popis') or '',
                vytvoril=owner,
                zmenil=owner,
            )
            _stamp(obj, obj_created)
            _set_fields(obj, obj_spec.get('fields') or {}, field_maps[obj_spec['typ']])
            objects[obj.nazev] = obj

        last_visit = created
        for raw_day, hour, obj_name, typ_zapisu, nadpis, text in spec['entries']:
            day = date.fromisoformat(raw_day)
            nastalo = _at(day, hour)
            last_visit = nastalo
            objekt = objects[obj_name] if obj_name else None
            entry = Entry.objects.create(
                salon=salon,
                zakaznik=customer,
                objekt=objekt,
                nastalo=nastalo,
                typ_zapisu=typ_zapisu,
                nadpis=nadpis,
                text=text,
                vytvoril=owner,
                zmenil=owner,
            )
            _stamp(entry, nastalo)

        for raw_day, obj_name, text, stav in spec['reminders']:
            day = date.fromisoformat(raw_day)
            objekt = objects[obj_name] if obj_name else None
            reminder = Reminder.objects.create(
                salon=salon,
                zakaznik=customer,
                objekt=objekt,
                termin=day,
                text=text,
                stav=stav,
                prirazeny=owner,
                vytvoril=owner,
            )
            if stav == ReminderStav.HOTOVO:
                stamp_at = _at(day, 8, 0)
            else:
                stamp_at = last_visit
            _stamp(reminder, stamp_at)


def seed_pawcare(*, salon_id: int = DEFAULT_SALON_ID, reset: bool = False) -> dict:
    salon, owner = _load_salon(salon_id)
    apply_preset(salon, 'vet')

    existing = Customer.objects.filter(salon=salon).exists()
    if existing and not reset:
        result = counts(salon)
        result['skip'] = True
        result['salon_id'] = salon.id
        result['reset'] = False
        return result

    if existing and reset:
        _wipe_kartoteka(salon)

    _seed_rows(salon, owner)
    result = counts(salon)
    result['skip'] = False
    result['salon_id'] = salon.id
    result['reset'] = reset
    return result
