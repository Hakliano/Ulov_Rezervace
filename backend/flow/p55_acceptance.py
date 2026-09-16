"""P5.5 STAGING acceptance sada — scoped wipe, žádný plošný reset konfigurace."""
from __future__ import annotations

from datetime import datetime, time, timedelta
from io import BytesIO
from zoneinfo import ZoneInfo

from django.db.models import Count, F, Q
from django.utils import timezone

from archivnik.models import (
    Asset,
    CustomFieldDef,
    CustomFieldValue,
    Customer,
    Entry,
    Object,
    ObjectType,
    Reminder,
    ReminderStav,
    Stav,
)
from flow.models import FlowUser
from partner_admin.models import MODUL_ARCHIVNIK
from partner_admin.services_moduly import nastav_modul
from rezervace.models import Rezervace, RezervaceSluzba, Zamestnanec
from salons.models import CenikPolozka, Salon

TZ = ZoneInfo('Europe/Prague')
TAG = 'p55-acceptance'
NOTE_PREFIX = 'P5.5'
EMAIL_SUFFIX = '@p55.ulov.local'
P53_TAG = 'p53-kartoteka'
P53_NOTE_PREFIX = 'P5.3'
P53_EMAIL_SUFFIX = '@p53.ulov.local'
DEFAULT_SALON_ID = 2
STANDALONE_OWNER_EMAIL = 'archivnik.solo@ulov.local'
PAGER_TARGET = 51
FILLER_PREFIX = 'P55 Strana'

EMAIL_A = f'jan.novak{EMAIL_SUFFIX}'
EMAIL_B = f'petr.bezobjektu{EMAIL_SUFFIX}'
EMAIL_C = f'anna.archiv{EMAIL_SUFFIX}'
EMAIL_D = f'karel.termin{EMAIL_SUFFIX}'
EMAIL_F = f'novy.host{EMAIL_SUFFIX}'


class Actor:
    username = 'p55-seed'


def owner_of(salon):
    return Zamestnanec.objects.filter(salon=salon, role='majitel').order_by('id').first()


def tagged_customers(salon):
    return Customer.objects.filter(salon=salon).filter(
        Q(email__iendswith=EMAIL_SUFFIX) | Q(poznamka__startswith=NOTE_PREFIX)
    )


def p53_customers(salon):
    return Customer.objects.filter(salon=salon).filter(
        Q(email__iendswith=P53_EMAIL_SUFFIX) | Q(poznamka__startswith=P53_NOTE_PREFIX)
    )


def _delete_customers(qs):
    uuids = list(qs.values_list('id', flat=True))
    if not uuids:
        return [], 0
    Object.objects.filter(zakaznik_id__in=uuids).update(cover=None)
    assets = list(Asset.objects.filter(zakaznik_id__in=uuids))
    keys = [a.storage_key for a in assets if a.storage_key]
    Asset.objects.filter(zakaznik_id__in=uuids).delete()
    Entry.objects.filter(zakaznik_id__in=uuids).delete()
    Reminder.objects.filter(zakaznik_id__in=uuids).delete()
    CustomFieldValue.objects.filter(objekt__zakaznik_id__in=uuids).delete()
    Object.objects.filter(zakaznik_id__in=uuids).delete()
    deleted, _ = qs.delete()
    _drop_storage(keys)
    return keys, deleted


def _drop_storage(keys):
    if not keys:
        return
    from archivnik.storage import delete_bytes
    for key in keys:
        try:
            delete_bytes(key)
        except Exception:
            pass


def wipe_tagged(salon):
    Rezervace.objects.filter(salon=salon, poznamka_interni=TAG).delete()
    keys, n = _delete_customers(tagged_customers(salon))
    return {'customers_deleted': n, 'asset_keys': keys}


def wipe_p53(salon):
    Rezervace.objects.filter(salon=salon, poznamka_interni=P53_TAG).delete()
    keys, n = _delete_customers(p53_customers(salon))
    return {'customers_deleted': n, 'asset_keys': keys}


def wipe_salon_kartoteka(salon):
    """Smaže jen evidenční kartotéku salonu. Obor / typy / pole / moduly nechá."""
    Rezervace.objects.filter(salon=salon, poznamka_interni__in=[TAG, P53_TAG]).delete()
    Object.objects.filter(salon=salon).update(cover=None)
    assets = list(Asset.objects.filter(salon=salon))
    keys = [a.storage_key for a in assets if a.storage_key]
    Asset.objects.filter(salon=salon).delete()
    Entry.objects.filter(salon=salon).delete()
    Reminder.objects.filter(salon=salon).delete()
    CustomFieldValue.objects.filter(objekt__salon=salon).delete()
    Object.objects.filter(salon=salon).delete()
    n, _ = Customer.objects.filter(salon=salon).delete()
    _drop_storage(keys)
    return {'customers_deleted': n, 'asset_keys': keys}


def _at(days, hour, minute=0):
    d = timezone.localdate() + timedelta(days=days)
    return datetime.combine(d, time(hour, minute), tzinfo=TZ)


def _types(salon):
    qs = list(ObjectType.objects.filter(salon=salon, aktivni=True).order_by('poradi', 'id'))
    if len(qs) < 1:
        raise SystemExit(f'Salon {salon.id} nemá aktivní ObjectType — P5.5 typy nevytváří.')
    if len(qs) == 1:
        return qs[0], qs[0]
    return qs[0], qs[1]


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


def _entry(salon, owner, zakaznik, text, *, objekt=None, typ='Poznámka', nadpis='', days=-2, hour=10):
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


def _png():
    from PIL import Image
    img = Image.new('RGB', (240, 240), (42, 92, 74))
    buf = BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


def _maybe_asset(salon, owner, zakaznik, objekt):
    try:
        from archivnik.storage import store_file
        raw = _png()
        asset_uuid, key, ctype, size = store_file(salon, raw, 'image/png', 'p55-jan-vlasy.png', 'fotografie')
    except Exception as exc:
        return None, str(exc)
    asset = Asset.objects.create(
        salon=salon,
        uuid=asset_uuid,
        zakaznik=zakaznik,
        objekt=objekt,
        druh='fotografie',
        nazev='p55-jan-vlasy.png',
        content_type=ctype,
        velikost=size,
        storage_key=key,
        vytvoril=owner,
    )
    Object.objects.filter(pk=objekt.pk).update(cover=asset)
    return asset, None


def _maybe_field_value(objekt):
    pole = CustomFieldDef.objects.filter(typ=objekt.typ, aktivni=True).order_by('poradi', 'id').first()
    if not pole:
        return None
    CustomFieldValue.objects.update_or_create(
        objekt=objekt, pole=pole, defaults={'hodnota': 'P5.5 acceptance'},
    )
    return pole.nazev


def _rez(salon, staff, sluzba, hour, jmeno, email):
    start = _at(0, hour, 0)
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
    return r


def seed_acceptance(salon, *, with_pager=False):
    actor = Actor()
    nastav_modul(salon, MODUL_ARCHIVNIK, True, actor)
    FlowUser.objects.filter(salon=salon, zamestnanec__role='majitel').update(visible_overview=True)

    owner = owner_of(salon)
    if not owner:
        raise SystemExit(f'Salon {salon.id} nemá majitele.')
    typ_a, typ_b = _types(salon)

    staff = (
        Zamestnanec.objects.filter(salon=salon, aktivni=True)
        .exclude(role='majitel')
        .order_by('poradi', 'id')
        .first()
    ) or Zamestnanec.objects.filter(salon=salon).first()
    if not staff:
        raise SystemExit(f'Salon {salon.id} nemá personál.')
    sluzba = CenikPolozka.objects.filter(salon=salon, aktivni=True).order_by('poradi', 'id').first()
    if not sluzba:
        sluzba = CenikPolozka.objects.create(
            salon=salon, nazev='P5.5 acceptance služba', cena=500, delka_minut=45, aktivni=True,
        )

    jan = _customer(
        salon, owner, 'Jan', 'Novák', EMAIL_A,
        telefon='777555001',
        poznamka='P5.5 Customer A — kompletní karta pro FLOW i Archivník.',
    )
    vlasy = Object.objects.create(
        salon=salon, zakaznik=jan, typ=typ_a, nazev='Vlasy Jan',
        popis='P5.5 object 1', vytvoril=owner, zmenil=owner,
    )
    vousy = Object.objects.create(
        salon=salon, zakaznik=jan, typ=typ_b, nazev='Vousy Jan',
        popis='P5.5 object 2', vytvoril=owner, zmenil=owner,
    )
    e1 = _entry(salon, owner, jan, 'Střih a foukaná, spokojený.', objekt=vlasy, typ='Ošetření', days=-14, hour=9)
    e2 = _entry(salon, owner, jan, 'Barva dle receptury.', objekt=vlasy, typ='Barvení', days=-7, hour=11)
    e3 = _entry(salon, owner, jan, 'Úprava vousů.', objekt=vousy, typ='Ošetření', days=-2, hour=15)
    Reminder.objects.create(
        salon=salon, zakaznik=jan, objekt=vlasy,
        termin=timezone.localdate() + timedelta(days=14),
        text='Kontrola barvy',
        stav=ReminderStav.AKTIVNI,
        vytvoril=owner,
    )
    field_name = _maybe_field_value(vlasy)
    asset, asset_err = _maybe_asset(salon, owner, jan, vlasy)

    petr = _customer(
        salon, owner, 'Petr', 'Bezobjektu', EMAIL_B,
        telefon='777555002',
        poznamka='P5.5 Customer B — aktivní, bez Object, Entry s object=NULL.',
    )
    e_null = _entry(salon, owner, petr, 'Zápis bez objektu.', objekt=None, typ='Poznámka', days=-1, hour=12)

    anna = _customer(
        salon, owner, 'Anna', 'Archivovaná', EMAIL_C,
        telefon='777555003',
        poznamka='P5.5 Customer C — archivovaný, data zůstávají čitelná.',
        stav=Stav.ARCHIVOVANY,
    )

    karel = _customer(
        salon, owner, 'Karel', 'Termín', EMAIL_D,
        telefon='777555004',
        poznamka='P5.5 Customer D — Object + prošlá Reminder.',
    )
    karel_obj = Object.objects.create(
        salon=salon, zakaznik=karel, typ=typ_a, nazev='Karel profil',
        vytvoril=owner, zmenil=owner,
    )
    _entry(salon, owner, karel, 'Poslední návštěva před termínem.', objekt=karel_obj, days=-10, hour=8)
    Reminder.objects.create(
        salon=salon, zakaznik=karel, objekt=karel_obj,
        termin=timezone.localdate() - timedelta(days=3),
        text='Očkování / kúra po termínu',
        stav=ReminderStav.AKTIVNI,
        vytvoril=owner,
    )

    walkin = Customer.objects.create(
        salon=salon,
        jmeno='Eliška',
        prijmeni='Bezmail',
        email='',
        telefon='777555005',
        poznamka='P5.5 Customer E — standalone Archivník bez e-mailu. FLOW nesmí matchovat k rezervaci.',
        vytvoril=owner,
        zmenil=owner,
    )

    fillers = 0
    if with_pager:
        have = Customer.objects.filter(salon=salon).count()
        need = max(0, PAGER_TARGET - have)
        for i in range(1, need + 1):
            _customer(
                salon, owner, 'P55', f'Strana {i:02d}', f'paginace{i:02d}{EMAIL_SUFFIX}',
                telefon=f'777556{i:03d}'[:40],
                poznamka=f'{NOTE_PREFIX} pager filler {i:02d}.',
            )
            fillers += 1

    rez_f = _rez(salon, staff, sluzba, 9, 'P55 Nový Host', EMAIL_F)
    rez_g = _rez(salon, staff, sluzba, 10, 'P55 Jan Novák', EMAIL_A)
    rez_h = _rez(salon, staff, sluzba, 11, 'P55 Bez E-mailu', '')

    return {
        'salon_id': salon.id,
        'owner_login': owner.prihlasovaci_jmeno or '',
        'jan': jan,
        'petr': petr,
        'anna': anna,
        'karel': karel,
        'walkin': walkin,
        'vlasy': vlasy,
        'vousy': vousy,
        'karel_obj': karel_obj,
        'entry_a': e1,
        'entry_null': e_null,
        'asset': asset,
        'asset_error': asset_err,
        'field': field_name,
        'fillers': fillers,
        'rez_f': rez_f,
        'rez_g': rez_g,
        'rez_h': rez_h,
        'typ_a': typ_a,
        'typ_b': typ_b,
        'entries_a': [e1, e2, e3],
    }


LEGACY_TABLES = ('flow_customercard', 'flow_customervisit')


def legacy_counts(salon):
    """Po P5.6B tabulky neexistují. Pokud zůstanou, nahlásit počty — nemazat potichu."""
    from django.db import connection

    tables = set(connection.introspection.table_names())
    present = [name for name in LEGACY_TABLES if name in tables]
    cards = 0
    visits = 0
    if 'flow_customercard' in tables:
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT COUNT(*) FROM flow_customercard WHERE salon_id = %s',
                [salon.id],
            )
            cards = cursor.fetchone()[0]
    if 'flow_customervisit' in tables:
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT COUNT(*) FROM flow_customervisit v '
                'INNER JOIN flow_customercard c ON c.id = v.card_id '
                'WHERE c.salon_id = %s',
                [salon.id],
            )
            visits = cursor.fetchone()[0]
    return {
        'customer_cards': cards,
        'customer_visits': visits,
        'tables_present': present,
    }


def config_snapshot(salon):
    from archivnik.models import Obor
    from partner_admin.models import PartnerModul
    return {
        'obory': Obor.objects.filter(salon=salon).count(),
        'object_types': ObjectType.objects.filter(salon=salon).count(),
        'custom_fields': CustomFieldDef.objects.filter(salon=salon).count(),
        'partner_moduly': PartnerModul.objects.filter(salon=salon).count(),
        'flow_users': FlowUser.objects.filter(salon=salon).count(),
        'staff': Zamestnanec.objects.filter(salon=salon).count(),
    }


def integrity_report(salon, extra_salon=None):
    from django.db.models.functions import Lower

    dupes = list(
        Customer.objects.filter(salon=salon)
        .exclude(email='')
        .annotate(em=Lower('email'))
        .values('em')
        .annotate(n=Count('id'))
        .filter(n__gt=1)
    )
    orphan_objects = Object.objects.filter(salon=salon, zakaznik__isnull=True).count()
    orphan_entries = Entry.objects.filter(salon=salon, zakaznik__isnull=True).count()
    object_other_salon = Object.objects.filter(salon=salon).exclude(zakaznik__salon_id=salon.id).count()
    object_foreign_qs = Object.objects.filter(zakaznik__salon=salon).exclude(salon_id=salon.id).count()
    entry_other_salon = Entry.objects.filter(salon=salon).exclude(zakaznik__salon_id=salon.id).count()
    entry_object_other_customer = (
        Entry.objects.filter(salon=salon, objekt__isnull=False)
        .exclude(objekt__zakaznik_id=F('zakaznik_id'))
        .count()
    )
    reminder_object_other = (
        Reminder.objects.filter(salon=salon, objekt__isnull=False)
        .exclude(objekt__zakaznik_id=F('zakaznik_id'))
        .count()
    )
    asset_other = Asset.objects.filter(salon=salon).exclude(zakaznik__salon_id=salon.id).count()

    global_cross = {
        'objects_salon_ne_zakaznik': Object.objects.exclude(salon_id=F('zakaznik__salon_id')).count(),
        'entries_salon_ne_zakaznik': Entry.objects.exclude(salon_id=F('zakaznik__salon_id')).count(),
        'entries_objekt_jiny_zakaznik': (
            Entry.objects.filter(objekt__isnull=False)
            .exclude(objekt__zakaznik_id=F('zakaznik_id'))
            .count()
        ),
        'reminders_objekt_jiny_zakaznik': (
            Reminder.objects.filter(objekt__isnull=False)
            .exclude(objekt__zakaznik_id=F('zakaznik_id'))
            .count()
        ),
        'assets_salon_ne_zakaznik': Asset.objects.exclude(salon_id=F('zakaznik__salon_id')).count(),
    }

    extra = None
    if extra_salon is not None:
        extra = {
            'salon_id': extra_salon.id,
            'customers': Customer.objects.filter(salon=extra_salon).count(),
            'shared_customer_uuids': Customer.objects.filter(
                salon=salon,
                uuid__in=Customer.objects.filter(salon=extra_salon).values_list('uuid', flat=True),
            ).count(),
        }

    illegal = (
        len(dupes)
        + orphan_objects
        + orphan_entries
        + object_other_salon
        + object_foreign_qs
        + entry_other_salon
        + entry_object_other_customer
        + reminder_object_other
        + asset_other
        + sum(global_cross.values())
        + (extra['shared_customer_uuids'] if extra else 0)
    )
    return {
        'salon_id': salon.id,
        'customers': Customer.objects.filter(salon=salon).count(),
        'objects': Object.objects.filter(salon=salon).count(),
        'entries': Entry.objects.filter(salon=salon).count(),
        'reminders': Reminder.objects.filter(salon=salon).count(),
        'assets': Asset.objects.filter(salon=salon).count(),
        'duplicate_emails': dupes,
        'orphan_objects': orphan_objects,
        'orphan_entries': orphan_entries,
        'object_customer_other_salon': object_other_salon,
        'object_belongs_other_salon_row': object_foreign_qs,
        'entry_customer_other_salon': entry_other_salon,
        'entry_object_other_customer': entry_object_other_customer,
        'reminder_object_other_customer': reminder_object_other,
        'asset_customer_other_salon': asset_other,
        'global_cross_tenant': global_cross,
        'extra_salon': extra,
        'illegal': illegal,
        'legacy': legacy_counts(salon),
        'config': config_snapshot(salon),
    }


def standalone_salon():
    owner = Zamestnanec.objects.filter(
        prihlasovaci_jmeno__iexact=STANDALONE_OWNER_EMAIL,
        role=Zamestnanec.ROLE_MAJITEL,
    ).first()
    return owner.salon if owner else None
