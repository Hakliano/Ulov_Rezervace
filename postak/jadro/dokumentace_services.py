"""Dokumentace — oprávnění, strom, validace souborů."""

from __future__ import annotations

import io
from pathlib import Path
import re
import uuid
import zipfile
from collections import defaultdict
from django.core.files.storage import default_storage
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError

from .dokumentace_models import REZIM_MOJE, REZIM_SDILENE, DokumentSlozka, DokumentSoubor

MAX_BYTES = 20 * 1024 * 1024
POVOLENE = frozenset({'pdf', 'docx', 'xlsx', 'pptx', 'txt', 'jpg', 'jpeg', 'png', 'webp'})
NAZEV_RE = re.compile(r'^[^\\/:*?"<>|]+$')


def _norm_pripona(raw: str) -> str:
    p = (raw or '').strip().lower().lstrip('.')
    return 'jpg' if p == 'jpeg' else p


def vycisti_nazev(raw: str) -> str:
    text = (raw or '').strip()
    if not text or not NAZEV_RE.match(text):
        raise ValidationError('Neplatný název.')
    if len(text) > 200:
        raise ValidationError('Název je příliš dlouhý.')
    return text


def rezim_vlastnik(user: User, rezim: str, vlastnik_param) -> tuple[str, User]:
    if rezim not in (REZIM_SDILENE, REZIM_MOJE):
        rezim = REZIM_SDILENE
    if rezim == REZIM_SDILENE:
        return rezim, user
    if user.is_superuser and vlastnik_param and str(vlastnik_param).isdigit():
        return rezim, User.objects.get(pk=int(vlastnik_param))
    return rezim, user


def muze_cist_slozku(user: User, slozka: DokumentSlozka) -> bool:
    if not user.is_authenticated:
        return False
    if slozka.rezim == REZIM_SDILENE:
        return True
    return slozka.vlastnik_id == user.pk or user.is_superuser


def muze_spravovat_rezim(user: User, rezim: str, vlastnik: User) -> bool:
    if rezim == REZIM_SDILENE:
        return user.is_superuser
    return user.pk == vlastnik.pk or user.is_superuser


def muze_spravovat_slozku(user: User, slozka: DokumentSlozka) -> bool:
    if not muze_cist_slozku(user, slozka):
        return False
    if slozka.rezim == REZIM_SDILENE:
        return user.is_superuser
    return slozka.vlastnik_id == user.pk or user.is_superuser


def muze_cist_soubor(user: User, soubor: DokumentSoubor) -> bool:
    return muze_cist_slozku(user, soubor.slozka)


def muze_spravovat_soubor(user: User, soubor: DokumentSoubor) -> bool:
    return muze_spravovat_slozku(user, soubor.slozka)


def queryset_slozek(rezim: str, vlastnik: User):
    qs = DokumentSlozka.objects.filter(rezim=rezim)
    if rezim == REZIM_MOJE:
        qs = qs.filter(vlastnik=vlastnik)
    return qs.select_related('vlastnik', 'vytvoril')


def strom_slozek(slozky):
    by_parent: dict[int | None, list] = defaultdict(list)
    for s in slozky:
        by_parent[s.parent_id].append(s)
    for items in by_parent.values():
        items.sort(key=lambda x: x.nazev.lower())

    def walk(parent_id, depth=0):
        rows = []
        for s in by_parent.get(parent_id, []):
            rows.append({'slozka': s, 'depth': depth})
            rows.extend(walk(s.pk, depth + 1))
        return rows

    return walk(None)


def potomci_ids(slozka: DokumentSlozka) -> set[int]:
    ids = {slozka.pk}
    front = [slozka.pk]
    while front:
        batch = list(
            DokumentSlozka.objects.filter(parent_id__in=front).values_list('pk', flat=True),
        )
        ids.update(batch)
        front = batch
    return ids


def lze_presunout_slozku(slozka: DokumentSlozka, cil_parent: DokumentSlozka | None) -> bool:
    if cil_parent is None:
        return True
    if cil_parent.pk == slozka.pk:
        return False
    forbidden = potomci_ids(slozka)
    return cil_parent.pk not in forbidden


def duplicitni_slozka(nazev: str, parent_id, rezim, vlastnik_id, vynechat_pk=None) -> bool:
    qs = DokumentSlozka.objects.filter(
        nazev=nazev,
        parent_id=parent_id,
        rezim=rezim,
    )
    if rezim == REZIM_MOJE:
        qs = qs.filter(vlastnik_id=vlastnik_id)
    else:
        qs = qs.filter(vlastnik__isnull=True)
    if vynechat_pk:
        qs = qs.exclude(pk=vynechat_pk)
    return qs.exists()


def duplicitni_soubor(nazev: str, slozka_id, vynechat_pk=None) -> bool:
    qs = DokumentSoubor.objects.filter(nazev=nazev, slozka_id=slozka_id)
    if vynechat_pk:
        qs = qs.exclude(pk=vynechat_pk)
    return qs.exists()


def _office_typ(data: bytes) -> str | None:
    if not data.startswith(b'PK\x03\x04'):
        return None
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            names = zf.namelist()
    except zipfile.BadZipFile:
        return None
    if any(n.startswith('word/') for n in names):
        return 'docx'
    if any(n.startswith('xl/') for n in names):
        return 'xlsx'
    if any(n.startswith('ppt/') for n in names):
        return 'pptx'
    return None


def over_soubor(upload, nazev_souboru: str) -> tuple[str, bytes]:
    if upload.size > MAX_BYTES:
        raise ValidationError('Soubor je větší než 20 MB.')
    data = upload.read()
    if len(data) > MAX_BYTES:
        raise ValidationError('Soubor je větší než 20 MB.')
    ext = _norm_pripona(Path(nazev_souboru).suffix)
    if ext not in POVOLENE:
        raise ValidationError('Nepovolený typ souboru.')
    skutecny = ''
    if data.startswith(b'%PDF'):
        skutecny = 'pdf'
    elif data.startswith(b'\xff\xd8\xff'):
        skutecny = 'jpg'
    elif data.startswith(b'\x89PNG\r\n\x1a\n'):
        skutecny = 'png'
    elif len(data) >= 12 and data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        skutecny = 'webp'
    elif ext == 'txt':
        if b'\x00' in data[:4096]:
            raise ValidationError('Textový soubor obsahuje binární data.')
        skutecny = 'txt'
    else:
        office = _office_typ(data)
        if office:
            skutecny = office
    if not skutecny or skutecny != ext:
        raise ValidationError('Obsah souboru neodpovídá příponě.')
    return ext, data


def nove_ulozene_jmeno(pripona: str) -> str:
    return f'{uuid.uuid4().hex}.{pripona}'


def precti_obsah(soubor: DokumentSoubor) -> bytes:
    name = (soubor.soubor.name or '').replace('\\', '/')
    if not name or '..' in name:
        raise ValidationError('Neplatná cesta souboru.')
    if not default_storage.exists(name):
        raise ValidationError('Soubor na úložišti neexistuje.')
    with default_storage.open(name, 'rb') as handle:
        return handle.read()


def soubor_mime(pripona: str) -> str:
    mapping = {
        'pdf': 'application/pdf',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        'txt': 'text/plain; charset=utf-8',
        'jpg': 'image/jpeg',
        'png': 'image/png',
        'webp': 'image/webp',
    }
    return mapping.get(pripona, 'application/octet-stream')


def pocet_polozek_ve_slozce(slozka: DokumentSlozka) -> int:
    return (
        slozka.soubory.count()
        + DokumentSlozka.objects.filter(parent=slozka).count()
    )


def assert_cisteni(user: User, slozka: DokumentSlozka):
    if not muze_cist_slozku(user, slozka):
        raise PermissionDenied


def assert_sprava(user: User, slozka: DokumentSlozka):
    if not muze_spravovat_slozku(user, slozka):
        raise PermissionDenied
