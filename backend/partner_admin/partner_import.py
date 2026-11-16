"""Bezpečný import partnerů do PotencialniKontakt (jen Moderník)."""

from __future__ import annotations

import json
import re
from contextlib import contextmanager
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction

from .models import PotencialniKontakt
from .potencialni import parse_import_json, sektor_podle_nazvu

NOVA_POLE = ('mesto', 'adresa', 'cast_obce', 'latitude', 'longitude')

PHONE_RE = re.compile(r'\D+')
PLACEHOLDER_EMAIL = re.compile(
    r'^(x+@x+(\.[a-z]+)?|xxxxx@xxxx\.cz|xxx@xxx\.(cz|com)|test@test\.(cz|com)|)$',
    re.IGNORECASE,
)


def normalizuj_email(raw: str) -> str:
    return (raw or '').strip().lower()


def je_placeholder_email(email: str) -> bool:
    email = normalizuj_email(email)
    if not email:
        return True
    if PLACEHOLDER_EMAIL.match(email):
        return True
    local, _, domain = email.partition('@')
    if not local or not domain:
        return True
    if 'xxxx' in email or re.search(r'x{4,}', local):
        return True
    return False


def platny_email_pro_import(raw: str) -> str | None:
    email = normalizuj_email(raw)
    if not email or je_placeholder_email(email):
        return None
    try:
        validate_email(email)
    except ValidationError:
        return None
    return email


def normalizuj_ico(raw: str) -> str:
    digits = PHONE_RE.sub('', raw or '')
    return digits.lstrip('0') or digits


def normalizuj_telefon(raw: str) -> str:
    digits = PHONE_RE.sub('', raw or '')
    if not digits:
        return ''
    if digits.startswith('00420') and len(digits) > 12:
        digits = digits[5:]
    elif digits.startswith('420') and len(digits) > 9:
        digits = digits[3:]
    if len(digits) >= 9:
        return digits[-9:]
    return digits


def _text(hodnota) -> str:
    if hodnota is None:
        return ''
    return str(hodnota).strip()


def _prvni(raw: dict, *klice: str) -> str:
    for klic in klice:
        if klic in raw and raw[klic] not in (None, ''):
            return _text(raw[klic])
    return ''


def normalizuj_souradnice(lat_raw, lon_raw) -> tuple[Decimal | None, Decimal | None]:
    if lat_raw in (None, '') or lon_raw in (None, ''):
        return None, None
    try:
        lat = Decimal(str(lat_raw).replace(',', '.'))
        lon = Decimal(str(lon_raw).replace(',', '.'))
    except (InvalidOperation, ValueError):
        return None, None
    if lat == 0 and lon == 0:
        return None, None
    return lat, lon


def _prazdne(val, nazev_pole: str) -> bool:
    if val is None:
        return True
    if nazev_pole in ('latitude', 'longitude'):
        return False
    return not str(val).strip()


def extrahuj_adresni(raw: dict) -> dict:
    adresa = _prvni(raw, 'adresa', 'address', 'ulice', 'street')
    lat, lon = normalizuj_souradnice(
        raw.get('latitude', raw.get('lat')),
        raw.get('longitude', raw.get('lon', raw.get('lng'))),
    )
    return {
        'mesto': _prvni(raw, 'mesto', 'město', 'city')[:120] or None,
        'adresa': adresa or None,
        'cast_obce': _prvni(raw, 'cast_obce', 'část obce', 'cast_obce_nazev', 'district')[:120] or None,
        'latitude': lat,
        'longitude': lon,
    }


def import_fingerprint(data: dict) -> str:
    return '|'.join([
        (data.get('jmeno') or '')[:80].casefold(),
        data.get('_nt_email') or '',
        data.get('_nt_telefon') or '',
        data.get('_nt_ico') or '',
    ])


def normalizuj_radek_partnera(raw: dict) -> dict:
    if not isinstance(raw, dict):
        raise ValidationError('Položka musí být objekt.')
    jmeno = _prvni(raw, 'company_name', 'jmeno', 'name', 'nazev', 'firma')
    if not jmeno:
        raise ValidationError('Každý záznam musí mít jméno.')
    email_raw = _prvni(raw, 'email', 'e-mail', 'mail')
    email = platny_email_pro_import(email_raw)
    if email_raw and not email and not je_placeholder_email(email_raw):
        raise ValidationError(f'Neplatný e-mail: {email_raw}')
    telefon = _prvni(raw, 'phone', 'telefon', 'tel')
    ico = _prvni(raw, 'ico', 'ičo', 'IČO')
    nt_tel = normalizuj_telefon(telefon)
    nt_ico = normalizuj_ico(ico)
    if not email and not nt_tel and not nt_ico:
        raise ValidationError('Chybí platný e-mail, telefon i IČO — nelze bezpečně zařadit.')
    adresni = extrahuj_adresni(raw)
    return {
        'jmeno': jmeno[:200],
        'email': email,
        'telefon': telefon[:200],
        'web': _prvni(raw, 'website', 'web', 'url')[:400],
        'ico': ico[:20],
        'sektor': sektor_podle_nazvu(jmeno),
        **adresni,
        '_nt_email': email or '',
        '_nt_telefon': nt_tel,
        '_nt_ico': nt_ico,
    }


@dataclass
class ImportReport:
    nacteno: int = 0
    jednoznacne: int = 0
    aktualizovano: int = 0
    vytvoreno: int = 0
    preskoceno: int = 0
    nejednoznacne: int = 0
    duplicitni_vstup: int = 0
    neplatne: list[str] = field(default_factory=list)
    nejednoznacne_priklady: list[str] = field(default_factory=list)
    statusy_zmeneny: list[str] = field(default_factory=list)
    pred_pocet: int = 0
    po_pocet: int = 0

    def as_dict(self) -> dict:
        return {
            'nacteno': self.nacteno,
            'UPDATE': self.aktualizovano,
            'INSERT': self.vytvoreno,
            'SKIP': self.preskoceno,
            'jednoznacne': self.jednoznacne,
            'konflikty': self.nejednoznacne,
            'duplicity_json': self.duplicitni_vstup,
            'neplatne': self.neplatne,
            'nejednoznacne_priklady': self.nejednoznacne_priklady[:20],
            'statusy_zmeneny': self.statusy_zmeneny,
            'pred_pocet': self.pred_pocet,
            'po_pocet': self.po_pocet,
        }


def _index_kontaktu() -> tuple[dict[str, list[int]], dict[str, list[int]], dict[str, list[int]]]:
    by_email: dict[str, list[int]] = {}
    by_phone: dict[str, list[int]] = {}
    by_ico: dict[str, list[int]] = {}
    for pk, email, telefon, ico in PotencialniKontakt.objects.values_list('pk', 'email', 'telefon', 'ico'):
        em = platny_email_pro_import(email or '')
        if em:
            by_email.setdefault(em, []).append(pk)
        ph = normalizuj_telefon(telefon)
        if ph:
            by_phone.setdefault(ph, []).append(pk)
        ic = normalizuj_ico(ico)
        if ic:
            by_ico.setdefault(ic, []).append(pk)
    return by_email, by_phone, by_ico


def najdi_shodu(
    data: dict,
    by_email: dict[str, list[int]],
    by_phone: dict[str, list[int]],
    by_ico: dict[str, list[int]],
) -> tuple[str, int | None]:
    """Vrátí ('match', pk) | ('ambiguous', None) | ('none', None)."""
    pouzite: list[tuple[str, set[int]]] = []

    if data['_nt_email']:
        ids = by_email.get(data['_nt_email'], [])
        if len(ids) > 1:
            return 'ambiguous', None
        if ids:
            pouzite.append(('email', {ids[0]}))

    if data['_nt_telefon']:
        ids = by_phone.get(data['_nt_telefon'], [])
        if len(ids) > 1:
            return 'ambiguous', None
        if ids:
            pouzite.append(('telefon', {ids[0]}))

    if data['_nt_ico']:
        ids = by_ico.get(data['_nt_ico'], [])
        if ids:
            pouzite.append(('ico', set(ids)))

    if not pouzite:
        return 'none', None

    if len(pouzite) == 1 and pouzite[0][0] == 'ico':
        return 'ambiguous', None

    prunik = pouzite[0][1].copy()
    for _, mnozina in pouzite[1:]:
        prunik &= mnozina
    if len(prunik) == 1:
        return 'match', next(iter(prunik))

    sjednoceni: set[int] = set()
    for _, mnozina in pouzite:
        sjednoceni |= mnozina
    if len(sjednoceni) > 1:
        return 'ambiguous', None
    if len(prunik) == 0 and len(pouzite) > 1:
        return 'ambiguous', None
    if len(pouzite) == 1 and len(pouzite[0][1]) == 1:
        return 'match', next(iter(pouzite[0][1]))
    return 'ambiguous', None


def _dopln_nova_pole(kontakt: PotencialniKontakt, data: dict) -> bool:
    changed = False
    for fld in NOVA_POLE:
        val = data.get(fld)
        if _prazdne(getattr(kontakt, fld), fld):
            if not _prazdne(val, fld):
                setattr(kontakt, fld, val)
                changed = True
    if changed:
        kontakt.save(update_fields=[*NOVA_POLE, 'upraveno'])
    return changed


def _snapshot_stavu() -> dict[int, str]:
    return dict(PotencialniKontakt.objects.values_list('pk', 'stav'))


def nacti_soubory(cesty: list[Path]) -> list:
    vse: list = []
    for cesta in cesty:
        raw = cesta.read_text(encoding='utf-8-sig')
        vse.extend(parse_import_json(json.loads(raw)))
    return vse


@contextmanager
def _import_transakce(dry_run: bool):
    with transaction.atomic():
        yield
        if dry_run:
            transaction.set_rollback(True)


def _popis_radku(data: dict) -> str:
    em = data.get('email') or '—'
    return f'{em} ({data["jmeno"][:40]})'


def spust_import(payloads: list, *, dry_run: bool = True) -> ImportReport:
    report = ImportReport()
    report.pred_pocet = PotencialniKontakt.objects.count()
    stav_pred = _snapshot_stavu()
    by_email, by_phone, by_ico = _index_kontaktu()
    videne: set[str] = set()

    with _import_transakce(dry_run):
        for i, raw in enumerate(payloads, start=1):
            report.nacteno += 1
            try:
                data = normalizuj_radek_partnera(raw)
            except (ValidationError, TypeError, ValueError) as exc:
                report.neplatne.append(f'řádek {i}: {exc}')
                continue

            fp = import_fingerprint(data)
            if fp in videne:
                report.duplicitni_vstup += 1
                continue
            videne.add(fp)

            shoda, pk = najdi_shodu(data, by_email, by_phone, by_ico)
            if shoda == 'ambiguous':
                report.nejednoznacne += 1
                if len(report.nejednoznacne_priklady) < 15:
                    report.nejednoznacne_priklady.append(_popis_radku(data))
                continue

            if shoda == 'match' and pk is not None:
                report.jednoznacne += 1
                kontakt = PotencialniKontakt.objects.get(pk=pk)
                if _dopln_nova_pole(kontakt, data):
                    report.aktualizovano += 1
                else:
                    report.preskoceno += 1
                continue

            if shoda == 'none':
                if data['_nt_email'] and data['_nt_email'] in by_email:
                    report.nejednoznacne += 1
                    continue
                novy = PotencialniKontakt.objects.create(
                    jmeno=data['jmeno'],
                    email=data['email'],
                    telefon=data['telefon'],
                    web=data['web'],
                    ico=data['ico'],
                    poznamka='',
                    stav=PotencialniKontakt.STAV_LEAD_PRED,
                    sektor=data['sektor'],
                    mesto=data.get('mesto'),
                    adresa=data.get('adresa'),
                    cast_obce=data.get('cast_obce'),
                    latitude=data.get('latitude'),
                    longitude=data.get('longitude'),
                )
                if data['_nt_email']:
                    by_email.setdefault(data['_nt_email'], []).append(novy.pk)
                if data['_nt_telefon']:
                    by_phone.setdefault(data['_nt_telefon'], []).append(novy.pk)
                if data['_nt_ico']:
                    by_ico.setdefault(data['_nt_ico'], []).append(novy.pk)
                report.vytvoreno += 1

    stav_po = _snapshot_stavu()
    for kid, stav in stav_pred.items():
        if kid in stav_po and stav_po[kid] != stav:
            report.statusy_zmeneny.append(f'id={kid}: {stav} → {stav_po[kid]}')
    report.po_pocet = PotencialniKontakt.objects.count()
    if dry_run:
        report.po_pocet = report.pred_pocet
    return report