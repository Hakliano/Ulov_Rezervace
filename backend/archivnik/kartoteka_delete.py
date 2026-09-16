"""Centrální výmaz jedné kartotéky Archivníka včetně fyzických souborů."""

from __future__ import annotations

from django.db import transaction

from archivnik.models import CustomFieldValue, Customer, Object
from archivnik.storage import BunnyUploadError, delete_stored_file


class KartotekaDeleteError(Exception):
    pass


def _bunny_keys(customer: Customer) -> list[str]:
    keys = []
    seen = set()
    for key in customer.soubory.exclude(storage_key='').values_list('storage_key', flat=True):
        if key in seen:
            continue
        seen.add(key)
        keys.append(key)
    return keys


def _smaz_db_strom(customer: Customer) -> None:
    objekty = list(customer.objekty.all())
    if objekty:
        Object.objects.filter(pk__in=[o.pk for o in objekty]).update(cover=None)
        CustomFieldValue.objects.filter(objekt__in=objekty).delete()
        for obj in objekty:
            obj.tagy.clear()
    customer.soubory.all().delete()
    customer.zapisy.all().delete()
    customer.pripominky.all().delete()
    customer.objekty.all().delete()
    customer.tagy.clear()
    customer.delete()


def smaz_kartoteku_zakaznika(salon, customer_uuid) -> None:
    """Bunny nejdřív (404=OK). Když zbývá soubor, DB se nesahe. Retry je stejné volání."""
    customer = (
        Customer.objects.filter(salon=salon, uuid=customer_uuid)
        .prefetch_related('soubory')
        .first()
    )
    if customer is None:
        raise KartotekaDeleteError('Zákazník v této provozovně neexistuje.')

    failures = []
    for key in _bunny_keys(customer):
        try:
            delete_stored_file(key)
        except BunnyUploadError as exc:
            failures.append(str(exc))
    if failures:
        raise KartotekaDeleteError(
            'Soubor na úložišti se nepodařilo odstranit. Kartotéka zůstala. '
            'Zkuste akci zopakovat. ' + failures[0]
        )

    with transaction.atomic():
        locked = Customer.objects.select_for_update().filter(pk=customer.pk, salon=salon).first()
        if locked is None:
            return
        _smaz_db_strom(locked)
