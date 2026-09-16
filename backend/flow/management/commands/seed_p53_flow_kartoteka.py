"""Čistá P5.3 testovací kartotéka pro salon 2. Nemaže P3/P4 konfiguraci."""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand
from django.utils import timezone

from archivnik.models import Customer, Entry, Object, ObjectType, Reminder, ReminderStav, Stav
from archivnik.services import apply_preset, primary_obor, salon_is_onboarded
from flow.models import FlowUser
from partner_admin.models import MODUL_ARCHIVNIK
from partner_admin.services_moduly import nastav_modul
from rezervace.models import Rezervace, RezervaceSluzba, Zamestnanec
from salons.models import CenikPolozka, Salon

TZ = ZoneInfo('Europe/Prague')
TAG = 'p53-kartoteka'
EMAIL_SUFFIX = '@p53.ulov.local'
SALON_ID = 2


class Actor:
    username = 'p53-seed'


class Command(BaseCommand):
    help = (
        'P5.3 testovací kartotéka (salon 2). Maže jen data s @p53.ulov.local / tagem. '
        'Obory, ObjectTypes, CustomFields a PartnerModul jinak nemění.'
    )

    def handle(self, *args, **options):
        salon = Salon.objects.filter(pk=SALON_ID).first()
        if not salon:
            raise SystemExit('Salon 2 neexistuje.')
        actor = Actor()
        nastav_modul(salon, MODUL_ARCHIVNIK, True, actor)
        FlowUser.objects.filter(salon=salon, zamestnanec__role='majitel').update(visible_overview=True)

        if not salon_is_onboarded(salon):
            apply_preset(salon, 'beauty')
            self.stdout.write('P5.3: salon 2 neměl Obor/typy — doplněn beauty preset.')

        obor = primary_obor(salon)
        typ, typ_created = ObjectType.objects.get_or_create(
            salon=salon,
            nazev='Pes',
            defaults={
                'obor': obor,
                'vyzaduje_nazev': True,
                'aktivni': True,
                'poradi': ObjectType.objects.filter(salon=salon).count() + 1,
            },
        )
        if typ_created:
            self.stdout.write('P5.3: doplněn ObjectType Pes (bez wipe existujících typů).')
        elif obor and typ.obor_id is None:
            typ.obor = obor
            typ.save(update_fields=['obor', 'upraveno'])

        staff = (
            Zamestnanec.objects.filter(salon=salon, aktivni=True)
            .exclude(role='majitel')
            .order_by('poradi', 'id')
            .first()
        ) or Zamestnanec.objects.filter(salon=salon).first()
        if not staff:
            raise SystemExit('Salon 2 nemá personál.')
        sluzba = CenikPolozka.objects.filter(salon=salon, aktivni=True).order_by('poradi', 'id').first()
        if not sluzba:
            sluzba = CenikPolozka.objects.create(
                salon=salon, nazev='P5.3 test služba', cena=500, delka_minut=45, aktivni=True,
            )

        _wipe(salon)
        owner = Zamestnanec.objects.filter(salon=salon, role='majitel').first()

        existujici = _customer(
            salon, owner, 'Jana', 'Existující', 'jana.existujici@p53.ulov.local',
            telefon='777111001', poznamka='P5.3 existující Customer pro kalendář.',
        )
        bez_objektu = _customer(
            salon, owner, 'Petr', 'Bezobjektu', 'petr.bezobjektu@p53.ulov.local',
            telefon='777111002', poznamka='P5.3 Customer bez Object.',
        )
        zapis_volny = _customer(
            salon, owner, 'Eva', 'Zápisová', 'eva.zapis@p53.ulov.local',
            telefon='777111003', poznamka='P5.3 Entry bez Object.',
        )
        Entry.objects.create(
            salon=salon, zakaznik=zapis_volny, objekt=None,
            typ_zapisu='Poznámka', text='Zápis bez objektu.',
            vytvoril=owner, zmenil=owner,
        )
        reminder_c = _customer(
            salon, owner, 'Karel', 'Připomínka', 'karel.pripominka@p53.ulov.local',
            telefon='777111004', poznamka='P5.3 Reminder + Max.',
        )
        maxik = Object.objects.create(
            salon=salon, zakaznik=reminder_c, typ=typ, nazev='Max',
            vytvoril=owner, zmenil=owner,
        )
        Entry.objects.create(
            salon=salon, zakaznik=reminder_c, objekt=maxik,
            typ_zapisu='Kontrola', text='Kontrola Max — bez komplikací.',
            vytvoril=owner, zmenil=owner,
        )
        Reminder.objects.create(
            salon=salon, zakaznik=reminder_c, objekt=maxik,
            termin=timezone.localdate() - timedelta(days=3),
            text='Očkování po termínu',
            stav=ReminderStav.AKTIVNI,
            vytvoril=owner,
        )
        archivovany = _customer(
            salon, owner, 'Anna', 'Archivovaná', 'anna.archiv@p53.ulov.local',
            telefon='777111005', poznamka='P5.3 archivovaný Customer.',
            stav=Stav.ARCHIVOVANY,
        )
        standalone_bez_mailu = Customer.objects.create(
            salon=salon, jmeno='Walkin', prijmeni='Bezmail', email='',
            telefon='777111006', poznamka='P5.3 standalone Customer bez e-mailu.',
            vytvoril=owner, zmenil=owner,
        )

        nrez = 0
        nrez += _rez(salon, staff, sluzba, 0, 9, 0, 'P53 Nový Host', 'novy.host@p53.ulov.local')
        nrez += _rez(salon, staff, sluzba, 0, 10, 0, 'P53 Jana Existující', 'jana.existujici@p53.ulov.local')
        nrez += _rez(salon, staff, sluzba, 0, 11, 0, 'P53 Bez E-mailu', '')
        nrez += _rez(salon, staff, sluzba, 0, 12, 0, 'P53 Anna Archivovaná', 'anna.archiv@p53.ulov.local')

        self.stdout.write(self.style.SUCCESS(
            f'P5.3 seed salon={salon.id}: customers='
            f'{Customer.objects.filter(salon=salon, email__iendswith=EMAIL_SUFFIX).count()}+'
            f'{int(bool(standalone_bez_mailu.pk))}, rezervace={nrez}, '
            f'existujici={existujici.uuid}, bez_objektu={bez_objektu.uuid}, '
            f'archivovany={archivovany.uuid}'
        ))


def _wipe(salon):
    Rezervace.objects.filter(salon=salon, poznamka_interni=TAG).delete()
    qs = Customer.objects.filter(salon=salon).filter(
        models_q_email_or_note(salon)
    )
    uuids = list(qs.values_list('id', flat=True))
    if uuids:
        Entry.objects.filter(zakaznik_id__in=uuids).delete()
        Reminder.objects.filter(zakaznik_id__in=uuids).delete()
        Object.objects.filter(zakaznik_id__in=uuids).delete()
        qs.delete()


def models_q_email_or_note(salon):
    from django.db.models import Q
    return Q(email__iendswith=EMAIL_SUFFIX) | Q(poznamka__startswith='P5.3')


def _customer(salon, owner, jmeno, prijmeni, email, *, telefon='', poznamka='', stav=Stav.AKTIVNI):
    return Customer.objects.create(
        salon=salon,
        jmeno=jmeno,
        prijmeni=prijmeni,
        email=email,
        telefon=telefon,
        poznamka=poznamka,
        stav=stav,
        vytvoril=owner,
        zmenil=owner,
    )


def _at(days, hour, minute=0):
    d = timezone.localdate() + timedelta(days=days)
    return datetime.combine(d, time(hour, minute), tzinfo=TZ)


def _rez(salon, staff, sluzba, days, hour, minute, jmeno, email):
    start = _at(days, hour, minute)
    delka = sluzba.delka_minut or 45
    r = Rezervace.objects.create(
        salon=salon,
        zamestnanec=staff,
        zacatek=start,
        konec=start + timedelta(minutes=delka),
        stav='potvrzeno',
        jmeno_host=jmeno,
        email_host=email,
        typ_vytvoreni='telefon',
        poznamka_interni=TAG,
    )
    RezervaceSluzba.objects.create(rezervace=r, sluzba=sluzba, poradi=0)
    return 1
