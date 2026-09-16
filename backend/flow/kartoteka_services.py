"""FLOW read proxy nad archivnik.models. Tenant = salon z FLOW session."""
from __future__ import annotations

from datetime import date

from django.conf import settings
from django.db.models import Prefetch
from django.utils import timezone

from archivnik.models import Customer, Entry, Object, Reminder, ReminderStav, Stav


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
        'typ_nazev': obj.typ.nazev if obj.typ_id else '',
        'stav': obj.stav,
    }


def _serialize_entry(entry: Entry) -> dict:
    objekt = entry.objekt
    return {
        'uuid': str(entry.uuid),
        'nastalo': entry.nastalo.isoformat() if entry.nastalo else None,
        'typ_zapisu': entry.typ_zapisu,
        'nadpis': entry.nadpis or '',
        'text': entry.text or '',
        'objekt_uuid': str(objekt.uuid) if objekt_id_safe(objekt) else None,
        'objekt_nazev': objekt.display_name if objekt else None,
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
        .select_related('objekt', 'objekt__typ')
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
