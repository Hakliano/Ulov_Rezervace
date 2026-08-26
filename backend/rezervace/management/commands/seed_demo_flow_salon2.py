"""Demo rezervace a karty pro salon 2 (Studio Krása) — prezentace FLOW."""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand
from django.utils import timezone

from flow.customer_card_models import CustomerCard, CustomerVisit
from flow.models import FlowUser
from rezervace.models import Rezervace, RezervaceSluzba, Zamestnanec, ZamestnanecRozvrh
from salons.models import CenikPolozka, Salon

TZ = ZoneInfo('Europe/Prague')
DEMO_TAG = 'demo-seed-salon2'

SLUZBY = [
    ('Střih dámský', 690, 45, False),
    ('Barvení celá hlava', 1890, 120, True),
    ('Melír fólie', 2490, 150, True),
    ('Keratinová kúra', 1290, 75, False),
    ('Střih + foukaná', 890, 60, False),
    ('Blond / odbarvení', 2790, 150, True),
]


class Command(BaseCommand):
    help = 'Naplní salon 2 prezentovatelnými rezervacemi a kartami zákazníků.'

    def handle(self, *args, **options):
        salon = Salon.objects.filter(pk=2).first()
        if not salon:
            raise SystemExit('Salon 2 neexistuje.')
        staff = _staff(salon)
        sluzby = _sluzby(salon)
        _enable_overview(salon)
        Rezervace.objects.filter(salon=salon, poznamka_interni=DEMO_TAG).delete()
        CustomerVisit.objects.filter(card__salon=salon, text__startswith='[demo]').delete()
        created = _rezervace(salon, staff, sluzby)
        cards = _karty(salon)
        self.stdout.write(self.style.SUCCESS(
            f'Demo FLOW: {created} rezervací, {cards} karet, personál {", ".join(s.jmeno for s in staff)}'
        ))


def _at(days, hour, minute=0):
    d = timezone.localdate() + timedelta(days=days)
    return datetime.combine(d, time(hour, minute), tzinfo=TZ)


def _staff(salon):
    qs = list(
        Zamestnanec.objects.filter(salon=salon, aktivni=True).exclude(role='majitel').order_by('poradi', 'id')
    )
    if not qs:
        qs = list(Zamestnanec.objects.filter(salon=salon).exclude(role='majitel')[:2])
    if len(qs) < 2:
        for name, spec, poradi in (('Markéta', 'Barvení, střihy', 0), ('Eva', 'Melíry, keratin', 1)):
            z, _ = Zamestnanec.objects.get_or_create(
                salon=salon, jmeno=name,
                defaults={'specializace': spec, 'poradi': poradi, 'role': 'zamestnanec', 'aktivni': True},
            )
            if z not in qs:
                qs.append(z)
    for z in qs:
        if not z.rozvrh.exists():
            for den in range(7):
                volno = den in (3, 6)
                ZamestnanecRozvrh.objects.get_or_create(
                    zamestnanec=z, den=den,
                    defaults={
                        'od': None if volno else time(9, 0),
                        'do': None if volno else time(17, 0),
                        'volno': volno,
                    },
                )
    return qs[:2]


def _sluzby(salon):
    out = {}
    for i, (nazev, cena, delka, rizikovy) in enumerate(SLUZBY):
        pol, _ = CenikPolozka.objects.get_or_create(
            salon=salon, nazev=nazev,
            defaults={
                'cena': cena, 'delka_minut': delka, 'rezerva_minut': 10,
                'poradi': i, 'aktivni': True, 'rizikovy': rizikovy,
            },
        )
        if pol.delka_minut != delka or pol.rizikovy != rizikovy:
            pol.delka_minut = delka
            pol.rizikovy = rizikovy
            pol.aktivni = True
            pol.save(update_fields=['delka_minut', 'rizikovy', 'aktivni'])
        out[nazev] = pol
    return out


def _enable_overview(salon):
    FlowUser.objects.filter(salon=salon, zamestnanec__role='majitel').update(visible_overview=True)


def _add(salon, staff, sluzba, start, stav, jmeno, email, *, zaloha=None, interni=''):
    delka = sluzba.delka_minut or 45
    r = Rezervace.objects.create(
        salon=salon,
        zamestnanec=staff,
        zacatek=start,
        konec=start + timedelta(minutes=delka),
        stav=stav,
        jmeno_host=jmeno,
        email_host=email,
        typ_vytvoreni='telefon',
        poznamka_interni=DEMO_TAG,
        poznamka_zakaznika=interni,
        dokonceno_at=start + timedelta(minutes=delka) if stav == 'dokonceno' else None,
    )
    RezervaceSluzba.objects.create(rezervace=r, sluzba=sluzba, poradi=0)
    if zaloha == 'ceka':
        r.zaloha_vyzadana_at = timezone.now() - timedelta(hours=6)
        r.zaloha_castka = 500
        r.save(update_fields=['zaloha_vyzadana_at', 'zaloha_castka'])
    elif zaloha == 'ok':
        r.zaloha_vyzadana_at = timezone.now() - timedelta(days=1)
        r.zaloha_ok_at = timezone.now() - timedelta(hours=12)
        r.zaloha_castka = 500
        r.save(update_fields=['zaloha_vyzadana_at', 'zaloha_ok_at', 'zaloha_castka'])
    elif zaloha == 'skip':
        r.zaloha_nepozadovana_at = timezone.now() - timedelta(hours=2)
        r.save(update_fields=['zaloha_nepozadovana_at'])
    return r


def _rezervace(salon, staff, sluzby):
    a, b = staff[0], staff[1]
    plan = [
        (-3, 9, 0, a, 'Střih dámský', 'dokonceno', 'Tereza Nováková', 'tereza.novakova@demo.cz', None, ''),
        (-3, 11, 0, b, 'Barvení celá hlava', 'dokonceno', 'Klára Svobodová', 'klara.svobodova@demo.cz', 'ok', ''),
        (-2, 10, 0, a, 'Střih + foukaná', 'dokonceno', 'Jana Dvořáková', 'jana.dvorakova@demo.cz', None, ''),
        (-2, 13, 0, b, 'Melír fólie', 'dokonceno', 'Petra Černá', 'petra.cerna@demo.cz', 'ok', 'Chce studený blond'),
        (-1, 9, 30, a, 'Keratinová kúra', 'dokonceno', 'Lucie Procházková', 'lucie.p@demo.cz', None, ''),
        (-1, 14, 0, b, 'Blond / odbarvení', 'no_show', 'Adéla Malá', 'adela.mala@demo.cz', 'ceka', ''),
        (0, 9, 0, a, 'Střih dámský', 'potvrzeno', 'Eliška Králová', 'eliska.kralova@demo.cz', 'skip', ''),
        (0, 10, 30, b, 'Barvení celá hlava', 'potvrzeno', 'Martina Veselá', 'martina.vesela@demo.cz', 'ceka', 'Barva 6.1'),
        (0, 13, 0, a, 'Střih + foukaná', 'ceka', 'Nikol Horáková', 'nikol.horakova@demo.cz', None, 'Nová zákaznice'),
        (0, 15, 0, b, 'Melír fólie', 'potvrzeno', 'Barbora Kučerová', 'barbora.kucerova@demo.cz', 'ok', ''),
        (1, 9, 0, a, 'Střih dámský', 'potvrzeno', 'Veronika Benešová', 'veronika.b@demo.cz', None, ''),
        (1, 11, 0, b, 'Keratinová kúra', 'potvrzeno', 'Alena Pokorná', 'alena.pokorna@demo.cz', None, ''),
        (1, 14, 0, a, 'Barvení celá hlava', 'potvrzeno', 'Simona Fialová', 'simona.fialova@demo.cz', 'ceka', ''),
        (2, 10, 0, b, 'Blond / odbarvení', 'potvrzeno', 'Kristýna Urbanová', 'kristyna.u@demo.cz', 'ok', ''),
        (2, 13, 30, a, 'Střih + foukaná', 'potvrzeno', 'Hana Marková', 'hana.markova@demo.cz', None, ''),
        (3, 9, 30, b, 'Melír fólie', 'potvrzeno', 'Iva Němcová', 'iva.nemcova@demo.cz', None, ''),
        (4, 11, 0, a, 'Střih dámský', 'potvrzeno', 'Monika Šťastná', 'monika.stastna@demo.cz', None, ''),
    ]
    n = 0
    for days, h, m, who, sl, stav, jmeno, email, zaloha, note in plan:
        _add(salon, who, sluzby[sl], _at(days, h, m), stav, jmeno, email, zaloha=zaloha, interni=note)
        n += 1
    return n


def _karty(salon):
    rows = [
        ('tereza.novakova@demo.cz', 'Tereza Nováková', '777 111 201', 'Dlouhé vlasy, bez amoniaku.'),
        ('klara.svobodova@demo.cz', 'Klára Svobodová', '777 111 202', 'Citlivá pokožka, Smartbond.'),
        ('martina.vesela@demo.cz', 'Martina Veselá', '777 111 208', 'Stálá zákaznice, barva 6.1.'),
        ('eliska.kralova@demo.cz', 'Eliška Králová', '777 111 207', 'Ráda krátký bob.'),
        ('barbora.kucerova@demo.cz', 'Barbora Kučerová', '777 111 210', 'Melír každé 8 týdny.'),
    ]
    n = 0
    for email, jmeno, telefon, note in rows:
        card, created = CustomerCard.objects.get_or_create(
            salon=salon, email=email,
            defaults={
                'jmeno': jmeno, 'telefon': telefon, 'poznamka': note,
                'stav': CustomerCard.STAV_AKTIVNI, 'confirmed_at': timezone.now(),
            },
        )
        if created or not card.visits.filter(text__startswith='[demo]').exists():
            CustomerVisit.objects.create(
                card=card,
                datum=timezone.localdate() - timedelta(days=12),
                text=f'[demo] {note}',
                autor_jmeno='Markéta',
            )
        n += 1
    return n
