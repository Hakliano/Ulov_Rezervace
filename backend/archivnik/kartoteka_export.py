"""Servisní ZIP export Archivníka. Nemění a nemaže data."""

from __future__ import annotations

import json
import re
import zipfile
from datetime import datetime, timezone as dt_timezone
from pathlib import Path

from django.core.management.base import CommandError
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Prefetch

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
    Tag,
)
from archivnik.storage import get_bytes
from salons.bunny import BunnyUploadError

EXPORT_VERSION = 1


def _iso(value):
    if value is None:
        return None
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return str(value)


def _safe_name(text, fallback='polozka') -> str:
    cleaned = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', '_', (text or '').strip())
    cleaned = re.sub(r'\s+', ' ', cleaned).strip(' .')
    return (cleaned[:80] or fallback)


def _customer_folder(customer: Customer) -> str:
    return f'{_safe_name(customer.display_name, "zakaznik")}__{customer.uuid.hex[:8]}'


def _asset_filename(asset: Asset) -> str:
    raw = Path(asset.nazev or '').name or 'soubor'
    stem = Path(raw).stem
    ext = Path(raw).suffix
    if not ext:
        if asset.content_type == 'application/pdf':
            ext = '.pdf'
        elif 'jpeg' in (asset.content_type or '') or 'jpg' in (asset.content_type or ''):
            ext = '.jpg'
        elif 'png' in (asset.content_type or ''):
            ext = '.png'
        elif 'webp' in (asset.content_type or ''):
            ext = '.webp'
        elif 'gif' in (asset.content_type or ''):
            ext = '.gif'
        else:
            ext = '.bin'
    return f'{_safe_name(stem, "soubor")}__{asset.uuid.hex[:8]}{ext}'


def _asset_relpath(customer_root: str, asset: Asset) -> str:
    name = _asset_filename(asset)
    if asset.objekt_id:
        obj_dir = _safe_name(asset.objekt.display_name, 'objekt')
        kind = 'fotografie' if asset.druh == 'fotografie' else 'dokumenty'
        return f'{customer_root}/{obj_dir}/{kind}/{name}'
    kind = 'fotografie-zakaznika' if asset.druh == 'fotografie' else 'dokumenty-zakaznika'
    return f'{customer_root}/{kind}/{name}'


def _customer_qs(salon):
    return (
        Customer.objects.filter(salon=salon)
        .prefetch_related(
            'tagy',
            Prefetch(
                'objekty',
                queryset=Object.objects.select_related('typ').prefetch_related(
                    'tagy',
                    Prefetch(
                        'hodnoty_poli',
                        queryset=CustomFieldValue.objects.select_related('pole'),
                    ),
                ),
            ),
            Prefetch('zapisy', queryset=Entry.objects.select_related('objekt')),
            Prefetch('pripominky', queryset=Reminder.objects.select_related('objekt')),
            Prefetch('soubory', queryset=Asset.objects.select_related('objekt', 'zapis')),
        )
    )


def _serialize_customer(customer: Customer, customer_root: str) -> dict:
    objekty = []
    for obj in customer.objekty.all():
        objekty.append({
            'uuid': str(obj.uuid),
            'nazev': obj.nazev,
            'display_name': obj.display_name,
            'popis': obj.popis,
            'stav': obj.stav,
            'typ_uuid': str(obj.typ.uuid) if obj.typ_id else None,
            'typ_nazev': obj.typ.nazev if obj.typ_id else None,
            'tagy': [t.nazev for t in obj.tagy.all()],
            'hodnoty_poli': [
                {
                    'pole_uuid': str(val.pole.uuid),
                    'nazev': val.pole.nazev,
                    'druh': val.pole.druh,
                    'hodnota': val.hodnota,
                }
                for val in obj.hodnoty_poli.all()
            ],
        })
    zapisy = []
    for row in customer.zapisy.all():
        zapisy.append({
            'uuid': str(row.uuid),
            'nastalo': _iso(row.nastalo),
            'typ_zapisu': row.typ_zapisu,
            'nadpis': row.nadpis,
            'text': row.text,
            'objekt_uuid': str(row.objekt.uuid) if row.objekt_id else None,
            'objekt_nazev': row.objekt.display_name if row.objekt_id else None,
        })
    pripominky = []
    for row in customer.pripominky.all():
        pripominky.append({
            'uuid': str(row.uuid),
            'termin': _iso(row.termin),
            'text': row.text,
            'stav': row.stav,
            'objekt_uuid': str(row.objekt.uuid) if row.objekt_id else None,
            'objekt_nazev': row.objekt.display_name if row.objekt_id else None,
        })
    soubory = []
    for asset in customer.soubory.all():
        soubory.append({
            'uuid': str(asset.uuid),
            'nazev': asset.nazev,
            'druh': asset.druh,
            'content_type': asset.content_type,
            'velikost': asset.velikost,
            'objekt_uuid': str(asset.objekt.uuid) if asset.objekt_id else None,
            'zapis_uuid': str(asset.zapis.uuid) if asset.zapis_id else None,
            'zip_cesta': _asset_relpath(customer_root, asset),
        })
    return {
        'zakaznik': {
            'uuid': str(customer.uuid),
            'jmeno': customer.jmeno,
            'prijmeni': customer.prijmeni,
            'display_name': customer.display_name,
            'telefon': customer.telefon,
            'email': customer.email,
            'adresa': customer.adresa,
            'poznamka': customer.poznamka,
            'stav': customer.stav,
            'tagy': [t.nazev for t in customer.tagy.all()],
            'vytvoreno': _iso(customer.vytvoreno),
        },
        'objekty': objekty,
        'zapisy': zapisy,
        'pripominky': pripominky,
        'soubory': soubory,
    }


def _serialize_types(types) -> list[dict]:
    rows = []
    for typ in types:
        rows.append({
            'uuid': str(typ.uuid),
            'nazev': typ.nazev,
            'vyzaduje_nazev': typ.vyzaduje_nazev,
            'aktivni': typ.aktivni,
            'obor_nazev': typ.obor.nazev if typ.obor_id else None,
            'pole': [
                {
                    'uuid': str(pole.uuid),
                    'nazev': pole.nazev,
                    'druh': pole.druh,
                    'volby': pole.volby,
                    'aktivni': pole.aktivni,
                }
                for pole in typ.pole.all()
            ],
        })
    return rows


def _dump(payload) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2, cls=DjangoJSONEncoder).encode('utf-8')


def _write_assets(zf: zipfile.ZipFile, customer: Customer, customer_root: str) -> int:
    count = 0
    for asset in customer.soubory.all():
        if not asset.storage_key:
            raise CommandError(f'Soubor {asset.nazev} nemá úložnou cestu. Export přerušen.')
        try:
            data, _ctype = get_bytes(asset.storage_key)
        except BunnyUploadError as exc:
            raise CommandError(
                f'Nelze stáhnout soubor {asset.nazev} ({asset.uuid}). Export přerušen. {exc}'
            ) from exc
        zf.writestr(_asset_relpath(customer_root, asset), data)
        count += 1
    return count


def _readme_single(customer: Customer) -> str:
    return (
        'Servisní export kartotéky Archivníka\n'
        '====================================\n\n'
        f'Zákazník: {customer.display_name}\n'
        f'UUID: {customer.uuid}\n'
        f'Provozovna: {customer.salon.name} (salon_id={customer.salon_id})\n'
        f'Vyexportováno: {datetime.now(dt_timezone.utc).isoformat()}\n\n'
        'Soubor kartoteka.json obsahuje identifikaci, kontakty, objekty, vlastní pole,\n'
        'zápisy, připomínky a metadata příloh. Fyzické soubory jsou ve složkách\n'
        'u příslušného objektu nebo u zákazníka.\n\n'
        'Tento ZIP je nezávislý na běhu aplikace. Nic v Archivníku se exportem nemění.\n'
    )


def _readme_partner(salon, customers) -> str:
    return (
        'Servisní exit export Archivníka\n'
        '===============================\n\n'
        f'Provozovna: {salon.name} (salon_id={salon.id})\n'
        f'Počet kartoték: {len(customers)}\n'
        f'Vyexportováno: {datetime.now(dt_timezone.utc).isoformat()}\n\n'
        'Obsahuje pouze data Archivníka této provozovny: zákazníky, objekty, typy,\n'
        'vlastní pole, zápisy, připomínky, přílohy a fyzické soubory.\n'
        'Neobsahuje hesla, tokeny, data jiných provozoven ani jiné produkty Moderníka.\n\n'
        'Export sám nic nemaže.\n'
    )


def export_customer_zip(salon, customer_uuid, dest: Path) -> dict:
    customer = _customer_qs(salon).filter(uuid=customer_uuid).first()
    if customer is None:
        raise CommandError('Zákazník v této provozovně neexistuje.')
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    root = _customer_folder(customer)
    used_type_ids = {obj.typ_id for obj in customer.objekty.all() if obj.typ_id}
    types = (
        ObjectType.objects.filter(salon=salon, pk__in=used_type_ids)
        .select_related('obor')
        .prefetch_related('pole')
        if used_type_ids else ObjectType.objects.none()
    )
    payload = {
        'export': {
            'typ': 'archivnik-single-customer',
            'verze': EXPORT_VERSION,
            'salon_id': salon.id,
            'salon_nazev': salon.name,
            'vyexportovano': datetime.now(dt_timezone.utc).isoformat(),
        },
        'typy_objektu': _serialize_types(types),
        **_serialize_customer(customer, root),
    }
    files = 0
    with zipfile.ZipFile(dest, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('README.txt', _readme_single(customer))
        zf.writestr(f'{root}/kartoteka.json', _dump(payload))
        files += _write_assets(zf, customer, root)
    return {
        'path': str(dest),
        'customer_uuid': str(customer.uuid),
        'files': files,
        'customers': 1,
    }


def export_partner_zip(salon, dest: Path) -> dict:
    customers = list(_customer_qs(salon).order_by('prijmeni', 'jmeno', 'id'))
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    types = ObjectType.objects.filter(salon=salon).select_related('obor').prefetch_related('pole')
    obory = list(Obor.objects.filter(salon=salon).order_by('poradi', 'nazev'))
    tags = list(Tag.objects.filter(salon=salon).order_by('nazev'))
    field_defs = list(
        CustomFieldDef.objects.filter(salon=salon).select_related('typ').order_by('typ__nazev', 'poradi', 'id')
    )
    manifest = {
        'export': {
            'typ': 'archivnik-partner-exit',
            'verze': EXPORT_VERSION,
            'salon_id': salon.id,
            'salon_nazev': salon.name,
            'vyexportovano': datetime.now(dt_timezone.utc).isoformat(),
            'pocet_zakazniku': len(customers),
        },
        'zakaznici': [
            {
                'uuid': str(c.uuid),
                'display_name': c.display_name,
                'email': c.email,
                'slozka': _customer_folder(c),
            }
            for c in customers
        ],
    }
    konfigurace = {
        'obory': [{'uuid': str(o.uuid), 'nazev': o.nazev} for o in obory],
        'typy_objektu': _serialize_types(types),
        'vlastni_pole': [
            {
                'uuid': str(p.uuid),
                'nazev': p.nazev,
                'druh': p.druh,
                'typ_uuid': str(p.typ.uuid),
                'typ_nazev': p.typ.nazev,
            }
            for p in field_defs
        ],
        'stitky': [{'uuid': str(t.uuid), 'nazev': t.nazev, 'rozsah': t.rozsah} for t in tags],
    }
    files = 0
    with zipfile.ZipFile(dest, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('README.txt', _readme_partner(salon, customers))
        zf.writestr('manifest.json', _dump(manifest))
        zf.writestr('konfigurace.json', _dump(konfigurace))
        for customer in customers:
            root = f'zakaznici/{_customer_folder(customer)}'
            payload = {
                'export': manifest['export'],
                **_serialize_customer(customer, root),
            }
            zf.writestr(f'{root}/kartoteka.json', _dump(payload))
            files += _write_assets(zf, customer, root)
    return {
        'path': str(dest),
        'files': files,
        'customers': len(customers),
        'customer_uuids': [str(c.uuid) for c in customers],
    }
