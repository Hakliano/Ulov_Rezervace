"""Pomocné funkce modulu Karta zákazníka (bez vazby na schéma rezervací)."""
from __future__ import annotations

from django.conf import settings
from django.db.models import Prefetch

from flow.customer_card_models import CustomerCard, CustomerVisit


def normalize_email(email: str) -> str:
    return (email or '').strip().lower()


def active_card_for_email(salon_id: int, email: str) -> CustomerCard | None:
    em = normalize_email(email)
    if not em:
        return None
    return (
        CustomerCard.objects.filter(
            salon_id=salon_id,
            email__iexact=em,
            stav=CustomerCard.STAV_AKTIVNI,
        )
        .first()
    )


def attach_customer_card_links(salon_id: int, rezervace_items: list[dict]) -> list[dict]:
    """Doplní customer_card_id do serializovaných rezervací (jen aktivní karty)."""
    emails = set()
    for item in rezervace_items:
        em = normalize_email(item.get('kontaktni_email') or '')
        if em:
            emails.add(em)
    if not emails:
        for item in rezervace_items:
            item['customer_card_id'] = None
        return rezervace_items

    cards = CustomerCard.objects.filter(
        salon_id=salon_id,
        stav=CustomerCard.STAV_AKTIVNI,
        email__in=list(emails),
    )
    # email__in is case-sensitive on some DBs — map case-insensitively
    by_email = {normalize_email(c.email): c.id for c in cards}
    # Also fetch iexact for any missed casing
    if len(by_email) < len(emails):
        for em in emails - set(by_email.keys()):
            c = active_card_for_email(salon_id, em)
            if c:
                by_email[em] = c.id

    for item in rezervace_items:
        em = normalize_email(item.get('kontaktni_email') or '')
        item['customer_card_id'] = by_email.get(em)
    return rezervace_items


def confirm_page_url(token: str) -> str:
    base = (
        getattr(settings, 'CUSTOMER_CARD_CONFIRM_BASE_URL', None)
        or getattr(settings, 'API_PUBLIC_BASE_URL', None)
        or 'https://api.ulovklienty.cz/api'
    ).rstrip('/')
    return f'{base}/flow/zakaznicka-karta/potvrdit/{token}/'


def card_with_visits(salon_id: int, card_id: int) -> CustomerCard | None:
    return (
        CustomerCard.objects.filter(salon_id=salon_id, pk=card_id)
        .prefetch_related(
            Prefetch('visits', queryset=CustomerVisit.objects.order_by('-datum', '-vytvoreno'))
        )
        .first()
    )


def client_ip(request) -> str | None:
    forwarded = (request.META.get('HTTP_X_FORWARDED_FOR') or '').split(',')[0].strip()
    if forwarded:
        return forwarded[:45]
    addr = request.META.get('REMOTE_ADDR') or ''
    return addr[:45] or None
