"""Demo FLOW data pro Salon Kudrlinka (pk 19) — použije existující ceník a personál."""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand
from django.utils import timezone

from flow.customer_card_models import CustomerCard, CustomerVisit
from flow.models import FlowUser
from rezervace.models import Rezervace, RezervaceSluzba, Zamestnanec, ZamestnanecRozvrh
from rezervace.services.staff_auth import ensure_owner_flow_user
from salons.models import CenikPolozka, OteviraciDoba, Salon

TZ = ZoneInfo('Europe/Prague')
DEMO_TAG = 'demo-seed-salon19'
SALON_PK = 19
OWNER_EMAIL = 'majitel.salon19@ulov.local'
OWNER_PASSWORD = 'majitelka123'

STAFF_FLOW = (
    ('Anna', 'anna.kudrlinka@ulov.local', 'Anna1234'),
    ('Eliška', 'eliska.kudrlinka@ulov.local', 'Eliska123'),
    ('Klára', 'klara.kudrlinka@ulov.local', 'Klara1234'),
)


class Command(BaseCommand):
    help = 'Naplní Kudrlinku FLOW účty, otevírací dobou a rezervacemi.'

    def handle(self, *args, **options):
        salon = Salon.objects.filter(pk=SALON_PK).first()
        if not salon:
            raise SystemExit('Salon Kudrlinka (pk 19) neexistuje.')
        _oteviraci_doba(salon)
        owner = _owner_flow(salon)
        staff = _staff_flow(salon)
        sluzby = _sluzby(salon)
        Rezervace.objects.filter(salon=salon, poznamka_interni=DEMO_TAG).delete()
        CustomerVisit.objects.filter(card__salon=salon, text__startswith='[demo]').delete()
        created = _rezervace(salon, staff, sluzby)
        cards = _karty(salon)
        self.stdout.write(self.style.SUCCESS(
            f'Kudrlinka: {created} rezervací, {cards} karet. '
            f'Manager: {OWNER_EMAIL} / {OWNER_PASSWORD}. '
            f'Staff FLOW: {", ".join(f"{s.jmeno} ({STAFF_FLOW[i][1]})" for i, s in enumerate(staff))}'
        ))
        if owner:
            self.stdout.write(f'Owner FLOW visible_overview={owner.visible_overview}')


def _at(days, hour, minute=0):
    d = timezone.localdate() + timedelta(days=days)
    return datetime.combine(d, time(hour, minute), tzinfo=TZ)


def _oteviraci_doba(salon):
    if OteviraciDoba.objects.filter(salon=salon).exists():
        return
    hours = [
        (0, time(7, 0), time(20, 0), False),
        (1, time(7, 0), time(20, 0), False),
        (2, time(7, 0), time(20, 0), False),
        (3, time(7, 0), time(20, 0), False),
        (4, time(7, 0), time(20, 0), False),
        (5, time(8, 0), time(16, 0), False),
        (6, None, None, True),
    ]
    for den, od, do, zavreno in hours:
        OteviraciDoba.objects.create(salon=salon, den=den, od=od, do=do, zavreno=zavreno)


def _owner_flow(salon):
    owner = Zamestnanec.objects.filter(salon=salon, role='majitel').first()
    if not owner:
        return None
    owner.prihlasovaci_jmeno = OWNER_EMAIL
    owner.set_password(OWNER_PASSWORD)
    owner.aktivni = True
    owner.save()
    user, _ = ensure_owner_flow_user(salon, email=OWNER_EMAIL)
    user.set_password(OWNER_PASSWORD)
    user.visible_overview = True
    user.aktivni = True
    user.save(update_fields=['password_hash', 'visible_overview', 'aktivni', 'upraveno'])
    return user


def _match_staff(salon, prefix):
    qs = Zamestnanec.objects.filter(salon=salon, aktivni=True).exclude(role='majitel')
    for z in qs:
        if (z.jmeno or '').startswith(prefix):
            return z
    return None


def _staff_flow(salon):
    out = []
    for i, (prefix, email, password) in enumerate(STAFF_FLOW):
        z = _match_staff(salon, prefix)
        if not z:
            continue
        z.prihlasovaci_jmeno = email
        z.set_password(password)
        z.aktivni = True
        z.save()
        fu, created = FlowUser.objects.get_or_create(
            zamestnanec=z,
            defaults={
                'salon': salon,
                'email': email,
                'aktivni': True,
                'visible_overview': i == 0,
            },
        )
        if not created:
            fu.email = email
            fu.aktivni = True
            fu.visible_overview = i == 0
        fu.set_password(password)
        fu.save()
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
        out.append(z)
    return out


def _sluzby(salon):
    out = {}
    for p in CenikPolozka.objects.filter(salon=salon, aktivni=True).order_by('poradi', 'id'):
        out[p.nazev] = p
    return out


def _pick_sluzba(sluzby, *names):
    for n in names:
        if n in sluzby:
            return sluzby[n]
    return next(iter(sluzby.values())) if sluzby else None


def _works(staff, when):
    den = when.weekday()
    row = staff.rozvrh.filter(den=den).first()
    if not row or row.volno or not row.od or not row.do:
        return False
    t = when.time()
    return row.od <= t < row.do


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
    if not staff or not sluzby:
        return 0
    by_prefix = {}
    for z in staff:
        for prefix, *_ in STAFF_FLOW:
            if z.jmeno.startswith(prefix):
                by_prefix[prefix] = z
    anna = by_prefix.get('Anna') or staff[0]
    eliska = by_prefix.get('Eliška') or staff[min(1, len(staff) - 1)]
    klara = by_prefix.get('Klára') or staff[-1]
    damsky = _pick_sluzba(sluzby, 'Dámský střih')
    pansky = _pick_sluzba(sluzby, 'Pánský střih')
    foukana = _pick_sluzba(sluzby, 'Střih + foukaná')
    barva = _pick_sluzba(sluzby, 'Barvení vlasů')
    balayage = _pick_sluzba(sluzby, 'Balayage')
    pece = _pick_sluzba(sluzby, 'Regenerační péče')
    styling = _pick_sluzba(sluzby, 'Společenský styling')
    detsky = _pick_sluzba(sluzby, 'Dětský střih')

    # Dny podle rozvrhu: Anna Po–St, Klára St–Pá, Eliška Pá–So.
    plan = [
        (-4, 9, 0, anna, damsky, 'dokonceno', 'Tereza Nováková', 'tereza.kudrlinka@demo.cz', None, ''),
        (-3, 10, 0, anna, barva, 'dokonceno', 'Klára Svobodová', 'klara.svobodova@demo.cz', 'ok', ''),
        (-2, 8, 30, anna, foukana, 'dokonceno', 'Jana Dvořáková', 'jana.dvorakova@demo.cz', None, ''),
        (-2, 11, 0, klara, pece, 'dokonceno', 'Petra Černá', 'petra.cerna@demo.cz', None, ''),
        (-1, 8, 0, klara, damsky, 'dokonceno', 'Lucie Procházková', 'lucie.p@demo.cz', None, ''),
        (-1, 12, 0, klara, balayage, 'no_show', 'Adéla Malá', 'adela.mala@demo.cz', 'ceka', ''),
        (0, 8, 0, klara, damsky, 'potvrzeno', 'Eliška Králová', 'eliska.kralova@demo.cz', 'skip', ''),
        (0, 10, 0, klara, barva, 'potvrzeno', 'Martina Veselá', 'martina.vesela@demo.cz', 'ceka', 'Chce teplejší tón'),
        (0, 13, 0, klara, foukana, 'ceka', 'Nikol Horáková', 'nikol.horakova@demo.cz', None, 'Nová zákaznice'),
        (1, 8, 30, klara, pansky, 'potvrzeno', 'Petr Beneš', 'petr.benes@demo.cz', None, ''),
        (1, 12, 0, eliska, balayage, 'potvrzeno', 'Barbora Kučerová', 'barbora.kucerova@demo.cz', 'ok', ''),
        (1, 15, 0, eliska, styling, 'potvrzeno', 'Alena Pokorná', 'alena.pokorna@demo.cz', None, ''),
        (2, 12, 30, eliska, detsky, 'potvrzeno', 'Sofie Marková', 'sofie.markova@demo.cz', None, ''),
        (2, 13, 30, eliska, pece, 'potvrzeno', 'Hana Marková', 'hana.markova@demo.cz', None, ''),
        (4, 9, 0, anna, damsky, 'potvrzeno', 'Veronika Benešová', 'veronika.b@demo.cz', None, ''),
        (4, 11, 0, anna, barva, 'potvrzeno', 'Simona Fialová', 'simona.fialova@demo.cz', 'ceka', ''),
        (5, 8, 30, anna, foukana, 'potvrzeno', 'Iva Němcová', 'iva.nemcova@demo.cz', None, ''),
        (5, 13, 0, anna, styling, 'potvrzeno', 'Monika Šťastná', 'monika.stastna@demo.cz', None, ''),
    ]
    n = 0
    for days, h, m, who, sl, stav, jmeno, email, zaloha, note in plan:
        if not who or not sl:
            continue
        start = _at(days, h, m)
        _add(salon, who, sl, start, stav, jmeno, email, zaloha=zaloha, interni=note)
        n += 1
    return n


def _karty(salon):
    rows = [
        ('tereza.kudrlinka@demo.cz', 'Tereza Nováková', '777 119 201', 'Dlouhé vlny, bez amoniaku.'),
        ('klara.svobodova@demo.cz', 'Klára Svobodová', '777 119 202', 'Balayage každé 3 měsíce.'),
        ('martina.vesela@demo.cz', 'Martina Veselá', '777 119 208', 'Stálá, barvení kořínků.'),
        ('eliska.kralova@demo.cz', 'Eliška Králová', '777 119 207', 'Ráda kratší střih.'),
        ('barbora.kucerova@demo.cz', 'Barbora Kučerová', '777 119 210', 'Blond balayage.'),
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
                autor_jmeno='Anna',
            )
        n += 1
    return n
