from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand
from django.utils import timezone

from io import BytesIO

from PIL import Image

from archivnik.models import (
    Asset, CustomFieldDef, CustomFieldValue, Customer, Entry, Object, ObjectType, Reminder, Tag, TagScope,
)
from archivnik.storage import store_file
from flow.models import FlowUser
from partner_admin.models import MODUL_ARCHIVNIK
from partner_admin.services import vytvor_noveho_partnera
from partner_admin.services_moduly import nastav_modul
from rezervace.models import Zamestnanec

OWNER_EMAIL = 'archivnik.solo@ulov.local'
OWNER_PASSWORD = 'majitelka123'
SALON_NAME = 'Archivník sólo'
TZ = ZoneInfo('Europe/Prague')


class Actor:
    username = 'archivnik-seed'


class Command(BaseCommand):
    help = (
        'Archivník-only provozovna bez FLOW + veterinární demo kartotéka. '
        'Bez --reset nikdy nemaže zákazníky, objekty, zápisy, připomínky ani Assety.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help=(
                'Smaže kartotéku této demo provozovny a nasadí ji znovu. '
                'Nespouštět z běžného deploye — smaže i nahrané fotografie a dokumenty.'
            ),
        )

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
        counts = _seed_kartoteka(salon, owner, reset=options['reset'])
        flow_count = FlowUser.objects.filter(salon=salon, aktivni=True).count()
        skip = ' skip_wipe=1' if counts.get('skip_wipe') else ''
        self.stdout.write(
            f'salon_id={salon.id} email={OWNER_EMAIL} flow_active={flow_count} '
            f'modul=archivnik zakaznici={counts["zakaznici"]} objekty={counts["objekty"]} '
            f'zapisy={counts["zapisy"]} pripominky={counts["pripominky"]} stitky={counts["stitky"]}'
            f'{skip}'
        )


def _at(days, hour=10, minute=0):
    d = timezone.localdate() + timedelta(days=days)
    return datetime.combine(d, time(hour, minute), tzinfo=TZ)


def _type(salon, nazev, poradi):
    row, _ = ObjectType.objects.get_or_create(
        salon=salon, nazev=nazev,
        defaults={'poradi': poradi, 'aktivni': True},
    )
    if row.poradi != poradi or not row.aktivni:
        row.poradi = poradi
        row.aktivni = True
        row.save(update_fields=['poradi', 'aktivni', 'upraveno'])
    return row


def _tag(salon, nazev, rozsah):
    row, _ = Tag.objects.get_or_create(
        salon=salon, nazev=nazev,
        defaults={'rozsah': rozsah},
    )
    return row


def _customer(salon, owner, jmeno, prijmeni, telefon, email='', adresa='', poznamka='', tagy=()):
    row = Customer.objects.create(
        salon=salon,
        jmeno=jmeno,
        prijmeni=prijmeni,
        telefon=telefon,
        email=email,
        adresa=adresa,
        poznamka=poznamka,
        vytvoril=owner,
        zmenil=owner,
    )
    if tagy:
        row.tagy.set(tagy)
    return row


def _object(salon, owner, zakaznik, typ, nazev, popis='', tagy=()):
    row = Object.objects.create(
        salon=salon,
        zakaznik=zakaznik,
        typ=typ,
        nazev=nazev,
        popis=popis,
        vytvoril=owner,
        zmenil=owner,
    )
    if tagy:
        row.tagy.set(tagy)
    return row


def _entry(salon, owner, zakaznik, text, days, hour=10, objekt=None, typ='Poznámka', nadpis=''):
    return Entry.objects.create(
        salon=salon,
        zakaznik=zakaznik,
        objekt=objekt,
        nastalo=_at(days, hour),
        typ_zapisu=typ,
        nadpis=nadpis,
        text=text,
        vytvoril=owner,
        zmenil=owner,
    )


def _png(color, size=320):
    img = Image.new('RGB', (size, size), color)
    buf = BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


_MIN_PDF = b"""%PDF-1.1
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/MediaBox[0 0 200 200]/Parent 2 0 R>>endobj
trailer<</Root 1 0 R>>
%%EOF
"""


def _field(salon, typ, nazev, druh, poradi):
    row, _ = CustomFieldDef.objects.get_or_create(
        salon=salon, typ=typ, nazev=nazev,
        defaults={'druh': druh, 'poradi': poradi, 'aktivni': True},
    )
    return row


def _value(objekt, pole, hodnota):
    CustomFieldValue.objects.update_or_create(objekt=objekt, pole=pole, defaults={'hodnota': hodnota})


def _asset(salon, owner, zakaznik, nazev, raw, content_type, druh, objekt=None, zapis=None):
    asset_uuid, key, ctype, size = store_file(salon, raw, content_type, nazev, druh)
    return Asset.objects.create(
        salon=salon,
        uuid=asset_uuid,
        zakaznik=zakaznik,
        objekt=objekt,
        zapis=zapis,
        druh=druh,
        nazev=nazev,
        content_type=ctype,
        velikost=size,
        storage_key=key,
        vytvoril=owner,
    )


def _reminder(salon, owner, zakaznik, text, days, objekt=None):
    return Reminder.objects.create(
        salon=salon,
        zakaznik=zakaznik,
        objekt=objekt,
        termin=timezone.localdate() + timedelta(days=days),
        text=text,
        prirazeny=owner,
        vytvoril=owner,
    )


def _kartoteka_counts(salon):
    return {
        'zakaznici': Customer.objects.filter(salon=salon).count(),
        'objekty': Object.objects.filter(salon=salon).count(),
        'zapisy': Entry.objects.filter(salon=salon).count(),
        'pripominky': Reminder.objects.filter(salon=salon).count(),
        'stitky': Tag.objects.filter(salon=salon).count(),
        'soubory': Asset.objects.filter(salon=salon).count(),
    }


def _seed_kartoteka(salon, owner, reset=False):
    if Customer.objects.filter(salon=salon).exists() and not reset:
        counts = _kartoteka_counts(salon)
        counts['skip_wipe'] = True
        return counts

    Asset.objects.filter(salon=salon).delete()
    CustomFieldValue.objects.filter(objekt__salon=salon).delete()
    CustomFieldDef.objects.filter(salon=salon).delete()
    Entry.objects.filter(salon=salon).delete()
    Reminder.objects.filter(salon=salon).delete()
    Object.objects.filter(salon=salon).delete()
    Customer.objects.filter(salon=salon).delete()
    Tag.objects.filter(salon=salon).delete()
    ObjectType.objects.filter(salon=salon, nazev='Objekt').delete()

    pes = _type(salon, 'Pes', 1)
    kocka = _type(salon, 'Kočka', 2)
    kralik = _type(salon, 'Králík', 3)
    ptak = _type(salon, 'Pták', 4)

    vip = _tag(salon, 'VIP', TagScope.ZAKAZNIK)
    novy = _tag(salon, 'Nový klient', TagScope.ZAKAZNIK)
    firemni = _tag(salon, 'Firemní', TagScope.ZAKAZNIK)
    senior = _tag(salon, 'Senior', TagScope.OBJEKT)
    stenatko = _tag(salon, 'Štěně / kotě', TagScope.OBJEKT)
    alergie = _tag(salon, 'Alergie', TagScope.OBE)
    kastrat = _tag(salon, 'Kastrát', TagScope.OBJEKT)

    eva = _customer(
        salon, owner, 'Eva', 'Nováková', '777 111 201',
        'eva.novakova@demo.vet', 'Husova 12, Poděbrady',
        'Chodí pravidelně, preferuje SMS.', tagy=[vip],
    )
    petr = _customer(
        salon, owner, 'Petr', 'Svoboda', '777 111 202',
        'petr.svoboda@demo.vet', 'Palackého 8, Nymburk',
        'Platí hotově.',
    )
    jana = _customer(
        salon, owner, 'Jana', 'Dvořáková', '777 111 203',
        'jana.dvorakova@demo.vet', 'Na Hrázi 4, Sadská',
        'Fakturace na IČO chovatelské stanice.', tagy=[firemni],
    )
    martin = _customer(
        salon, owner, 'Martin', 'Horák', '777 111 204',
        adresa='Hlavní 21, Velký Osek', poznamka='Bez e-mailu, volat dopoledne.',
    )
    lucie = _customer(
        salon, owner, 'Lucie', 'Černá', '777 111 205',
        'lucie.cerna@demo.vet', 'Jiráskova 3, Poděbrady',
        'Tři kočky, citlivá na cenu vakcín.', tagy=[vip, alergie],
    )
    klara = _customer(
        salon, owner, 'Klára', 'Benešová', '777 111 206',
        'klara.benesova@demo.vet', 'Školní 9, Pečky',
    )
    tomas = _customer(
        salon, owner, 'Tomáš', 'Procházka', '777 111 207',
        'tomas.prochazka@demo.vet', 'U Nádraží 2, Kolín',
        'Exoti — ptáci.',
    )
    martina = _customer(
        salon, owner, 'Martina', 'Veselá', '777 111 208',
        'martina.vesela@demo.vet', tagy=[novy],
    )
    eliska = _customer(
        salon, owner, 'Eliška', 'Králová', '777 111 209',
        'eliska.kralova@demo.vet', 'Komenského 15, Poděbrady',
    )
    adam = _customer(
        salon, owner, 'Adam', 'Malý', '777 111 210',
        'adam.maly@demo.vet', tagy=[novy],
    )
    barbora = _customer(
        salon, owner, 'Barbora', 'Kučerová', '777 111 211',
        'barbora.kucerova@demo.vet', 'Polní 7, Libice',
    )
    iva = _customer(
        salon, owner, 'Iva', 'Němcová', '777 111 212',
        'iva.nemcova@demo.vet',
        poznamka='Zatím bez zvířete — čeká na převzetí z útulku.', tagy=[novy],
    )
    alena = _customer(
        salon, owner, 'Alena', 'Pokorná', '777 111 213',
        'alena.pokorna@demo.vet', 'Zahradní 18, Nymburk',
        'Pes + kočka, jezdí spolu.',
    )

    maxp = _object(salon, owner, eva, pes, 'Max', 'Labrador, 7 let, 32 kg.', tagy=[senior])
    bara = _object(salon, owner, eva, pes, 'Bára', 'Jorkšír, 4 roky.')
    mourek = _object(salon, owner, eva, kocka, 'Mourek', 'Evropská krátkosrstá, kastrovaný.', tagy=[kastrat])
    micka = _object(salon, owner, petr, kocka, 'Micka', 'Britská, 5 let.', tagy=[kastrat])
    rocky = _object(salon, owner, jana, pes, 'Rocky', 'Golden retriever, chov.')
    luna = _object(salon, owner, jana, kocka, 'Luna', 'Norská lesní, 3 roky.', tagy=[kastrat])
    usak = _object(salon, owner, martin, kralik, 'Ušák', 'Beran, 2 roky.')
    fik = _object(salon, owner, martin, kralik, 'Fík', 'Zakrslý beran, 8 měsíců.', tagy=[stenatko])
    felix = _object(salon, owner, lucie, kocka, 'Felix', 'Mainská mývalí, astma.', tagy=[alergie, senior])
    mina = _object(salon, owner, lucie, kocka, 'Mína', 'Siamská, 2 roky.', tagy=[kastrat])
    kaja = _object(salon, owner, lucie, kocka, 'Kája', 'Kotě, 5 měsíců.', tagy=[stenatko])
    ares = _object(salon, owner, klara, pes, 'Ares', 'Německý ovčák, služební výcvik.')
    rio = _object(salon, owner, tomas, ptak, 'Rio', 'Andulka, samec.')
    kik = _object(salon, owner, tomas, ptak, 'Kiki', 'Korela, 1 rok.')
    dunka = _object(salon, owner, martina, pes, 'Dunka', 'Kříženec, 6 let.')
    ben = _object(salon, owner, martina, pes, 'Ben', 'Beagle, 3 roky.')
    coco = _object(salon, owner, eliska, kocka, 'Coco', 'Ragdoll, 4 roky.', tagy=[kastrat])
    punta = _object(salon, owner, adam, pes, 'Punťa', 'Štěně border kolie, 4 měsíce.', tagy=[stenatko])
    hedvika = _object(salon, owner, barbora, kralik, 'Hedvika', 'Zakrslý honák.')
    gump = _object(salon, owner, alena, pes, 'Gump', 'Jezevčík, 9 let.', tagy=[senior])
    zofie = _object(salon, owner, alena, kocka, 'Žofie', 'Domácí, 6 let.', tagy=[kastrat])

    _entry(salon, owner, eva, 'Preferuje SMS, e-mail jen na kopii nálezů.', -40, typ='Kontakt', nadpis='Komunikace')
    _entry(salon, owner, eva, 'Souhlasí s připomínkami očkování 14 dní předem.', -12, typ='Poznámka')
    _entry(salon, owner, jana, 'Fakturovat na chovatelskou stanici Zlatý Klas, IČO na kartě v šanonu.', -30, typ='Fakturace')
    _entry(salon, owner, lucie, 'U Felixe nepoužívat spreje — astma. Mína snáší běžné preparáty.', -18, 9, nadpis='Alergie v domácnosti')
    _entry(salon, owner, martin, 'Nemá e-mail. Volat dopoledne, odpoledne je v práci.', -8, typ='Kontakt')
    _entry(salon, owner, iva, 'Objednala se na převzetí kočky z útulku. Zatím bez karty zvířete.', -2, 16, typ='Poznámka', nadpis='Čeká na zvíře')
    _entry(salon, owner, adam, 'První návštěva — štěně z chovu, očkovací průkaz přinese příště.', -5, typ='Poznámka')

    _entry(salon, owner, eva, 'Roční prohlídka, mírný nadváha. Doporučena dieta a kontrola za 8 týdnů.', -21, 9, maxp, 'Prohlídka', 'Kontrola hmotnosti')
    max_ocko = _entry(salon, owner, eva, 'Očkování vzteklina + kombinovaná. Bez reakce.', -21, 10, maxp, 'Očkování')
    _entry(salon, owner, eva, 'Střižení drápků, uši v pořádku.', -6, 11, bara, 'Ošetření')
    _entry(salon, owner, eva, 'Kastrace hojená bez komplikací. Stehy ven za 10 dní.', -90, 8, mourek, 'Zákrok', 'Po kastraci')
    _entry(salon, owner, petr, 'Očkování, odčervení. Majitel hlásí zvracení po mléku — vynechat.', -14, 10, micka, 'Očkování')
    _entry(salon, owner, jana, 'Před výstavou: srst v pořádku, doporučen šampon. Krevní obraz v normě.', -11, 9, rocky, 'Prohlídka')
    _entry(salon, owner, jana, 'Odčervení, kontrola zubů.', -11, 10, luna, 'Ošetření')
    _entry(salon, owner, martin, 'Přerostlé zuby — úprava. Dieta seno ad libitum.', -9, 15, usak, 'Ošetření', 'Zuby')
    _entry(salon, owner, martin, 'První očkování myxomatóza / mor.', -4, 9, fik, 'Očkování')
    _entry(salon, owner, lucie, 'Dušnost po spreji v domácnosti. Inhalace, klid, kontrola za týden.', -7, 8, felix, 'Akutní', 'Astma')
    _entry(salon, owner, lucie, 'Očkování, kastrovaná, bez nálezu.', -20, 14, mina, 'Očkování')
    _entry(salon, owner, lucie, 'První vakcinace kotěte, odčervení. Váha 1,8 kg.', -3, 10, kaja, 'Očkování', 'První dávka')
    _entry(salon, owner, klara, 'Kulhání PZP po výcviku. Klid 10 dní, nesteroidy dle schématu.', -10, 8, ares, 'Ortopedie')
    _entry(salon, owner, tomas, 'Oříznutí zobáku a drápků. Trus v normě.', -15, 11, rio, 'Ošetření')
    _entry(salon, owner, tomas, 'Nová korela, vstupní prohlídka. Doporučena klec větší.', -2, 13, kik, 'Prohlídka')
    _entry(salon, owner, martina, 'Ušní zánět vlevo, výplach + kapky 7 dní.', -8, 9, dunka, 'Ošetření')
    _entry(salon, owner, martina, 'Očkování, čipy čtečka OK.', -8, 10, ben, 'Očkování')
    _entry(salon, owner, eliska, 'Roční prohlídka, zuby mírný kámen — příště dentální hygiena.', -16, 10, coco, 'Prohlídka')
    _entry(salon, owner, adam, 'Vstupní prohlídka štěněte, odčervení. Harmonogram vakcinace vysvětlen.', -5, 9, punta, 'Prohlídka')
    _entry(salon, owner, barbora, 'Kožní plíseň podezření — seškrab odeslán. Izolace od dětí.', -6, 12, hedvika, 'Laboratoř')
    _entry(salon, owner, alena, 'Senior: srdce šelest 2/6, doporučeno echo. Zatím bez léků.', -13, 8, gump, 'Kardiologie')
    _entry(salon, owner, alena, 'Očkování, kastrovaná, výborný stav.', -13, 9, zofie, 'Očkování')

    _reminder(salon, owner, eva, 'Kontrola hmotnosti Maxe (dieta)', 10, maxp)
    _reminder(salon, owner, lucie, 'Kontrola astmatu — Felix', 3, felix)
    _reminder(salon, owner, lucie, 'Druhá dávka vakcíny — Kája', 18, kaja)
    _reminder(salon, owner, klara, 'Kontrola kulhání Ares', 1, ares)
    _reminder(salon, owner, adam, 'Druhé očkování Punťa', 16, punta)
    _reminder(salon, owner, barbora, 'Zavolat výsledek seškrabu — Hedvika', 0, hedvika)
    _reminder(salon, owner, alena, 'Objednat echo srdce — Gump', 7, gump)
    _reminder(salon, owner, iva, 'Zavolat, zda už má kočku z útulku', 4)
    _reminder(salon, owner, eliska, 'Dentální hygiena Coco', 25, coco)

    pes_plemeno = _field(salon, pes, 'Plemeno', 'text', 1)
    pes_narozeni = _field(salon, pes, 'Datum narození', 'datum', 2)
    pes_cip = _field(salon, pes, 'Číslo čipu', 'text', 3)
    pes_hmotnost = _field(salon, pes, 'Hmotnost', 'cislo', 4)
    pes_kastr = _field(salon, pes, 'Kastrace', 'ano_ne', 5)
    _field(salon, kocka, 'Plemeno', 'text', 1)
    _field(salon, kocka, 'Datum narození', 'datum', 2)
    _field(salon, kocka, 'Číslo čipu', 'text', 3)
    kocka_kastr = _field(salon, kocka, 'Kastrace', 'ano_ne', 4)
    _field(salon, kralik, 'Plemeno', 'text', 1)
    _field(salon, kralik, 'Datum narození', 'datum', 2)
    _field(salon, ptak, 'Druh', 'text', 1)

    _value(maxp, pes_plemeno, 'Labrador retriever')
    _value(maxp, pes_narozeni, '2019-04-12')
    _value(maxp, pes_cip, '203098765432109')
    _value(maxp, pes_hmotnost, '32')
    _value(maxp, pes_kastr, 'ne')
    _value(micka, kocka_kastr, 'ano')
    _value(rocky, pes_plemeno, 'Golden retriever')
    _value(rocky, pes_cip, '203011122233344')

    profil = _asset(salon, owner, eva, 'Max-profil.png', _png((42, 92, 74)), 'image/png', 'fotografie', objekt=maxp)
    _asset(salon, owner, eva, 'Max-detail.png', _png((90, 58, 32)), 'image/png', 'fotografie', objekt=maxp)
    micka_foto = _asset(salon, owner, petr, 'Micka.png', _png((120, 90, 70)), 'image/png', 'fotografie', objekt=micka)
    _asset(
        salon, owner, eva, 'ockovaci-prukaz.pdf', _MIN_PDF, 'application/pdf', 'dokument',
        objekt=maxp, zapis=max_ocko,
    )
    _asset(salon, owner, eva, 'laboratorni-vysledky.pdf', _MIN_PDF, 'application/pdf', 'dokument', objekt=maxp)
    _asset(salon, owner, eva, 'souhlas-gdpr.pdf', _MIN_PDF, 'application/pdf', 'dokument')
    felix_foto = _asset(salon, owner, lucie, 'Felix.png', _png((60, 70, 90)), 'image/png', 'fotografie', objekt=felix)
    Object.objects.filter(pk=maxp.pk).update(cover=profil)
    Object.objects.filter(pk=micka.pk).update(cover=micka_foto)
    Object.objects.filter(pk=felix.pk).update(cover=felix_foto)

    counts = _kartoteka_counts(salon)
    counts['skip_wipe'] = False
    return counts
