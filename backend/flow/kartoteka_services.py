"""FLOW read proxy nad archivnik.models. Tenant = salon z FLOW session."""
from __future__ import annotations

from datetime import date

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Prefetch
from django.utils import timezone

from archivnik.models import Customer, Entry, Object, ObjectType, Reminder, ReminderStav, Stav
from archivnik.services import object_type_allowed_for_assign
from flow.auth import flow_zam
from rezervace.models import Rezervace


LIST_PAGE_SIZE_DEFAULT = 50
LIST_PAGE_SIZE_MAX = 100
DETAIL_ENTRY_LIMIT = 5


def normalize_email(email: str) -> str:
    return (email or '').strip().lower()


def customer_for_email(salon_id: int, email: str) -> Customer | None:
    """Jednoznačná shoda salon + normalizovaný e-mail. Bez e-mailu = žádný match."""
    em = normalize_email(email)
    if not em:
        return None
    return (
        Customer.objects.filter(salon_id=salon_id, email__iexact=em)
        .exclude(email='')
        .first()
    )


def attach_archivnik_customer_links(salon_id: int, rezervace_items: list[dict]) -> list[dict]:
    """Doplní archivnik_customer_uuid do serializovaných rezervací (runtime, bez FK)."""
    from partner_admin.models import MODUL_ARCHIVNIK
    from partner_admin.services_moduly import modul_je_aktivni

    if not modul_je_aktivni(salon_id, MODUL_ARCHIVNIK):
        for item in rezervace_items:
            item['archivnik_customer_uuid'] = None
        return rezervace_items
    emails = set()
    for item in rezervace_items:
        em = normalize_email(item.get('kontaktni_email') or '')
        if em:
            emails.add(em)
    by_email: dict[str, str] = {}
    if emails:
        found = Customer.objects.filter(
            salon_id=salon_id,
            email__in=list(emails),
        ).exclude(email='')
        by_email = {normalize_email(c.email): str(c.uuid) for c in found}
        missing = emails - set(by_email.keys())
        for em in missing:
            c = customer_for_email(salon_id, em)
            if c:
                by_email[em] = str(c.uuid)
    for item in rezervace_items:
        em = normalize_email(item.get('kontaktni_email') or '')
        item['archivnik_customer_uuid'] = by_email.get(em)
    return rezervace_items


def _display_name(customer: Customer) -> str:
    return customer.display_name


def serialize_customer_list_item(customer: Customer) -> dict:
    return {
        'uuid': str(customer.uuid),
        'jmeno': customer.jmeno,
        'prijmeni': customer.prijmeni,
        'display_name': _display_name(customer),
        'email': customer.email or '',
        'telefon': customer.telefon or '',
        'stav': customer.stav,
    }


def _serialize_object(obj: Object) -> dict:
    return {
        'uuid': str(obj.uuid),
        'nazev': obj.nazev or '',
        'display_name': obj.display_name,
        'typ_uuid': str(obj.typ.uuid) if obj.typ_id else None,
        'typ_nazev': obj.typ.nazev if obj.typ_id else '',
        'stav': obj.stav,
    }


def _serialize_entry(entry: Entry) -> dict:
    objekt = entry.objekt
    autor = entry.vytvoril
    return {
        'uuid': str(entry.uuid),
        'nastalo': entry.nastalo.isoformat() if entry.nastalo else None,
        'typ_zapisu': entry.typ_zapisu,
        'nadpis': entry.nadpis or '',
        'text': entry.text or '',
        'objekt_uuid': str(objekt.uuid) if objekt_id_safe(objekt) else None,
        'objekt_nazev': objekt.display_name if objekt else None,
        'autor': autor.jmeno if autor else None,
    }


def objekt_id_safe(objekt) -> bool:
    return bool(objekt is not None and getattr(objekt, 'uuid', None))


def _serialize_reminder(row: Reminder, *, dnes: date) -> dict:
    objekt = row.objekt
    return {
        'uuid': str(row.uuid),
        'termin': row.termin.isoformat() if row.termin else None,
        'text': row.text,
        'prosla': bool(row.termin and row.termin < dnes),
        'objekt_uuid': str(objekt.uuid) if objekt_id_safe(objekt) else None,
        'objekt_nazev': objekt.display_name if objekt else None,
    }


def archivnik_customer_url(customer: Customer) -> str:
    base = (getattr(settings, 'ARCHIVNIK_PUBLIC_URL', None) or '/archivnik/').rstrip('/')
    return f'{base}/?zakaznik={customer.uuid}'


def customer_qs(salon_id: int):
    return Customer.objects.filter(salon_id=salon_id)


def list_customers(salon_id: int, *, q: str = '', stav: str = '', page: int = 1, page_size: int = LIST_PAGE_SIZE_DEFAULT):
    qs = customer_qs(salon_id).order_by('prijmeni', 'jmeno', 'id')
    q = (q or '').strip()
    if q:
        from django.db.models import Q
        qs = qs.filter(
            Q(jmeno__icontains=q)
            | Q(prijmeni__icontains=q)
            | Q(email__icontains=q)
            | Q(telefon__icontains=q)
        )
    if stav in (Stav.AKTIVNI, Stav.ARCHIVOVANY):
        qs = qs.filter(stav=stav)

    page_size = max(1, min(int(page_size or LIST_PAGE_SIZE_DEFAULT), LIST_PAGE_SIZE_MAX))
    page = max(1, int(page or 1))
    total = qs.count()
    offset = (page - 1) * page_size
    items = list(qs[offset:offset + page_size])
    pages = max(1, (total + page_size - 1) // page_size) if total else 1
    return {
        'vysledky': [serialize_customer_list_item(c) for c in items],
        'stranka': page,
        'page_size': page_size,
        'celkem': total,
        'celkem_stranek': pages,
    }


def customer_detail(salon_id: int, customer_uuid) -> dict | None:
    customer = (
        customer_qs(salon_id)
        .filter(uuid=customer_uuid)
        .prefetch_related(
            Prefetch(
                'objekty',
                queryset=Object.objects.select_related('typ').order_by('nazev', 'id'),
            ),
        )
        .first()
    )
    if not customer:
        return None
    entries = list(
        Entry.objects.filter(salon_id=salon_id, zakaznik_id=customer.id)
        .select_related('objekt', 'objekt__typ', 'vytvoril')
        .order_by('-nastalo', '-vytvoreno')[:DETAIL_ENTRY_LIMIT]
    )
    reminders_qs = list(
        Reminder.objects.filter(
            salon_id=salon_id,
            zakaznik_id=customer.id,
            stav=ReminderStav.AKTIVNI,
        )
        .select_related('objekt', 'objekt__typ')
        .order_by('termin', 'id')
    )
    dnes = timezone.localdate()
    reminders = [_serialize_reminder(r, dnes=dnes) for r in reminders_qs]
    return {
        **serialize_customer_list_item(customer),
        'poznamka': customer.poznamka or '',
        'objekty': [_serialize_object(o) for o in customer.objekty.all()],
        'posledni_zapisy': [_serialize_entry(e) for e in entries],
        'pripominky': reminders,
        'ma_aktivni_pripominku': any(not r['prosla'] for r in reminders),
        'ma_proslou_pripominku': any(r['prosla'] for r in reminders),
        'archivnik_url': archivnik_customer_url(customer),
    }


class KartotekaError(Exception):
    def __init__(self, status: int, detail: str, extra: dict | None = None):
        super().__init__(detail)
        self.status = status
        self.detail = detail
        self.extra = extra or {}

    def as_response(self):
        from rest_framework.response import Response
        payload = {'detail': self.detail, **self.extra}
        return Response(payload, status=self.status)


def split_kontaktni_jmeno(value: str) -> tuple[str, str]:
    """Poslední slovo = příjmení, zbytek jméno. Jedno slovo = jen příjmení."""
    parts = (value or '').strip().split()
    if not parts:
        return '', ''
    if len(parts) == 1:
        return '', parts[0][:160]
    prijmeni = parts[-1][:160]
    jmeno = ' '.join(parts[:-1])[:120]
    return jmeno, prijmeni


def actor_zamestnanec(user):
    zam = flow_zam(user)
    if zam is None or not getattr(zam, 'pk', None):
        raise KartotekaError(403, 'Nelze určit zaměstnance pro zápis.')
    if zam.salon_id != user.salon_id:
        raise KartotekaError(403, 'Nelze určit zaměstnance pro zápis.')
    return zam


def _active_customer_or_error(salon_id, customer_uuid) -> Customer:
    customer = customer_qs(salon_id).filter(uuid=customer_uuid).first()
    if not customer:
        raise KartotekaError(404, 'Zákazník nenalezen.')
    if customer.stav == Stav.ARCHIVOVANY:
        raise KartotekaError(
            409,
            'Zákazník je v archivu.',
            extra={'uuid': str(customer.uuid), 'stav': customer.stav},
        )
    return customer


def _load_rezervace(salon_id, rezervace_id) -> Rezervace:
    try:
        pk = int(rezervace_id)
    except (TypeError, ValueError):
        raise KartotekaError(404, 'Rezervace nenalezena.')
    rez = Rezervace.objects.filter(salon_id=salon_id, pk=pk).first()
    if not rez:
        raise KartotekaError(404, 'Rezervace nenalezena.')
    return rez


def create_customer_from_flow(user, data: dict) -> dict:
    """Create-or-return Customer. E-mail povinný. Žádný merge podle jména/telefonu."""
    actor = actor_zamestnanec(user)
    salon_id = user.salon_id
    data = data or {}

    rezervace_id = data.get('rezervace_id')
    rezervace = None
    if rezervace_id not in (None, ''):
        rezervace = _load_rezervace(salon_id, rezervace_id)

    if rezervace is not None:
        email = normalize_email(rezervace.kontaktni_email or '')
        jmeno, prijmeni = split_kontaktni_jmeno(rezervace.kontaktni_jmeno or '')
        telefon = (data.get('telefon') or '').strip()[:40]
    else:
        email = normalize_email(data.get('email') or '')
        if (data.get('prijmeni') or '').strip() or (data.get('jmeno') or '').strip():
            jmeno = (data.get('jmeno') or '').strip()[:120]
            prijmeni = (data.get('prijmeni') or '').strip()[:160]
        else:
            jmeno, prijmeni = split_kontaktni_jmeno(data.get('kontaktni_jmeno') or '')
        telefon = (data.get('telefon') or '').strip()[:40]

    if not email:
        raise KartotekaError(400, 'E-mail je povinný.')
    from django.core.validators import validate_email
    try:
        validate_email(email)
    except ValidationError:
        raise KartotekaError(400, 'Neplatný e-mail.')
    if not prijmeni:
        raise KartotekaError(400, 'Zadejte jméno zákazníka.')

    existing = customer_for_email(salon_id, email)
    if existing:
        return _customer_create_payload(existing, created=False)

    customer = Customer(
        salon_id=salon_id,
        jmeno=jmeno,
        prijmeni=prijmeni,
        email=email,
        telefon=telefon,
        stav=Stav.AKTIVNI,
        vytvoril=actor,
        zmenil=actor,
    )
    try:
        with transaction.atomic():
            customer.save()
    except IntegrityError:
        raced = customer_for_email(salon_id, email)
        if raced:
            return _customer_create_payload(raced, created=False)
        raise KartotekaError(400, 'Zákazník s tímto e-mailem už v provozovně existuje.')
    return _customer_create_payload(customer, created=True)


def _customer_create_payload(customer: Customer, *, created: bool) -> dict:
    status = 201 if created else (409 if customer.stav == Stav.ARCHIVOVANY else 200)
    payload = {
        'vytvoreno': created,
        'zakaznik': customer_detail(customer.salon_id, customer.uuid),
    }
    if customer.stav == Stav.ARCHIVOVANY and not created:
        payload['detail'] = 'Zákazník je v archivu.'
    return {'status': status, 'body': payload}


def create_entry_from_flow(user, customer_uuid, data: dict) -> dict:
    actor = actor_zamestnanec(user)
    salon_id = user.salon_id
    data = data or {}
    customer = _active_customer_or_error(salon_id, customer_uuid)
    text = (data.get('text') or '').strip()
    if not text:
        raise KartotekaError(400, 'Zadejte text zápisu.')

    objekt = None
    raw_obj = data.get('objekt_uuid', None)
    if raw_obj not in (None, ''):
        objekt = (
            Object.objects.filter(salon_id=salon_id, uuid=raw_obj)
            .select_related('zakaznik', 'typ')
            .first()
        )
        if not objekt:
            raise KartotekaError(404, 'Objekt nenalezen.')
        if objekt.zakaznik_id != customer.id:
            raise KartotekaError(404, 'Objekt nenalezen.')

    entry = Entry(
        salon_id=salon_id,
        zakaznik=customer,
        objekt=objekt,
        typ_zapisu=(data.get('typ_zapisu') or 'Poznámka').strip() or 'Poznámka',
        nadpis=(data.get('nadpis') or '').strip()[:200],
        text=text,
        vytvoril=actor,
        zmenil=actor,
    )
    try:
        entry.save()
    except ValidationError as exc:
        raise KartotekaError(400, _validation_detail(exc)) from exc
    return _serialize_entry(entry)


def create_object_from_flow(user, customer_uuid, data: dict) -> dict:
    actor = actor_zamestnanec(user)
    salon_id = user.salon_id
    data = data or {}
    customer = _active_customer_or_error(salon_id, customer_uuid)
    typ_uuid = data.get('typ_uuid')
    if not typ_uuid:
        raise KartotekaError(400, 'Zadejte typ objektu.')
    typ = ObjectType.objects.filter(salon_id=salon_id, uuid=typ_uuid).select_related('obor').first()
    if not typ:
        raise KartotekaError(404, 'Typ objektu nenalezen.')
    if not object_type_allowed_for_assign(customer.salon, typ):
        raise KartotekaError(400, 'Tento typ nepatří k oboru kartotéky.')
    nazev = (data.get('nazev') or '').strip()
    if typ.vyzaduje_nazev and not nazev:
        raise KartotekaError(400, 'Zadejte název.')
    obj = Object(
        salon_id=salon_id,
        zakaznik=customer,
        typ=typ,
        nazev=nazev,
        stav=Stav.AKTIVNI,
        vytvoril=actor,
        zmenil=actor,
    )
    try:
        obj.save()
    except ValidationError as exc:
        raise KartotekaError(400, _validation_detail(exc)) from exc
    return _serialize_object(obj)


def list_assignable_object_types(salon) -> list[dict]:
    qs = (
        ObjectType.objects.filter(salon=salon, aktivni=True)
        .select_related('obor')
        .order_by('poradi', 'nazev')
    )
    return [
        {
            'uuid': str(t.uuid),
            'nazev': t.nazev,
            'vyzaduje_nazev': t.vyzaduje_nazev,
            'obor_uuid': str(t.obor.uuid) if t.obor_id else None,
        }
        for t in qs
        if object_type_allowed_for_assign(salon, t)
    ]


def _validation_detail(exc) -> str:
    if hasattr(exc, 'message_dict'):
        parts = []
        for key, msgs in exc.message_dict.items():
            parts.extend(str(m) for m in msgs)
        return '; '.join(parts) or str(exc)
    if getattr(exc, 'messages', None):
        return '; '.join(str(m) for m in exc.messages)
    return str(exc)
