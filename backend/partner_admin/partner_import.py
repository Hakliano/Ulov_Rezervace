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
DOPLNITELNA = ('email', 'telefon', 'web', 'ico', 'mesto', 'adresa', 'cast_obce')

PHONE_RE = re.compile(r'\D+')
PLACEHOLDER_EMAIL = re.compile(
    r'^(x+@x+(\.[a-z]+)?|xxxxx@xxxx\.cz|xxx@xxx\.(cz|com)|test@test\.(cz|com)|)$',
    re.IGNORECASE,
)

IMPORT_LOCK_KEY = 'partner_admin:potencialni_import_commit'
IMPORT_TOKEN_PREFIX = 'partner_admin:import_token:'
IMPORT_LOCK_TTL = 600
PG_ADVISORY_LOCK_ID = 91337421


class ImportZamcenError(Exception):
    """Jiný commit importu právě běží."""


class ImportNahledZastaralError(Exception):
    """Náhled už neodpovídá aktuální databázi."""


class ImportTokenPouzitError(Exception):
    """Náhled byl už potvrzen nebo vypršel."""


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
        digits = digits[-9:]
    else:
        return ''
    if len(set(digits)) == 1:
        return ''
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
    if not adresa:
        adresa = _prvni(raw, 'description', 'popis')
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
    zmeny: list[dict] = field(default_factory=list)
    pred_pocet: int = 0
    po_pocet: int = 0

    def as_dict(self) -> dict:
        return {
            'nacteno': self.nacteno,
            'UPDATE': self.aktualizovano,
            'INSERT': self.vytvoreno,
            'SKIP': self.preskoceno,
            'BEZE_ZMENY': self.preskoceno,
            'jednoznacne': self.jednoznacne,
            'konflikty': self.nejednoznacne,
            'KONFLIKT': self.nejednoznacne,
            'zmeny': self.zmeny,
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
    """('match', pk) | ('ambiguous', None) | ('none', None).

    Hlasují jen identifikátory, které v DB někdo má. Průnik právě jednoho
    kontaktu je UPDATE. Prázdný průnik nebo víc než jeden kontakt je konflikt.
    """
    hlasy: list[set[int]] = []
    for klic, index in (
        (data['_nt_email'], by_email),
        (data['_nt_telefon'], by_phone),
        (data['_nt_ico'], by_ico),
    ):
        if not klic:
            continue
        ids = index.get(klic, [])
        if ids:
            hlasy.append(set(ids))
    if not hlasy:
        return 'none', None
    prunik = set.intersection(*hlasy)
    if len(prunik) == 1:
        return 'match', next(iter(prunik))
    return 'ambiguous', None


def _nesouhlasi(kontakt: PotencialniKontakt, data: dict) -> str:
    """Vyplněný identifikátor na kontaktu se nesmí lišit od importu."""
    dvojice = (
        ('e-mail', data['_nt_email'], platny_email_pro_import(kontakt.email or '') or ''),
        ('telefon', data['_nt_telefon'], normalizuj_telefon(kontakt.telefon)),
        ('IČO', data['_nt_ico'], normalizuj_ico(kontakt.ico)),
    )
    for nazev, prichozi, stavajici in dvojice:
        if prichozi and stavajici and prichozi != stavajici:
            return f'{nazev} patří jinému provozu'
    return ''


def _dopln_prazdna_pole(kontakt: PotencialniKontakt, data: dict) -> list[str]:
    changed: list[str] = []
    for fld in DOPLNITELNA:
        if fld == 'telefon' and not data.get('_nt_telefon'):
            continue
        if fld == 'email' and not data.get('email'):
            continue
        if fld == 'ico' and not data.get('_nt_ico'):
            continue
        val = data.get(fld)
        if _prazdne(getattr(kontakt, fld), fld) and not _prazdne(val, fld):
            setattr(kontakt, fld, val)
            changed.append(fld)
    if kontakt.latitude is None and kontakt.longitude is None:
        if data.get('latitude') is not None and data.get('longitude') is not None:
            kontakt.latitude = data['latitude']
            kontakt.longitude = data['longitude']
            changed.extend(('latitude', 'longitude'))
    if changed:
        kontakt.save(update_fields=[*changed, 'upraveno'])
    return changed


def _snapshot_stavu() -> dict[int, str]:
    return dict(PotencialniKontakt.objects.values_list('pk', 'stav'))


def report_podpis(report: ImportReport) -> dict:
    return {
        'nacteno': report.nacteno,
        'create': report.vytvoreno,
        'update': report.aktualizovano,
        'beze_zmeny': report.preskoceno,
        'konflikt': report.nejednoznacne,
        'neplatne': len(report.neplatne),
        'pred_pocet': report.pred_pocet,
        'duplicity_json': report.duplicitni_vstup,
    }


def podpis_souhlasi(ulozeny: dict, report: ImportReport) -> bool:
    return ulozeny == report_podpis(report)


def _kolize_telefonu_v_davce(
    data: dict,
    telefon_v_davce: dict[str, int],
    shoda: str,
    pk: int | None,
    kontakt: PotencialniKontakt | None = None,
) -> str:
    nt_tel = data['_nt_telefon']
    if not nt_tel:
        return ''
    vlastnik = telefon_v_davce.get(nt_tel)
    if vlastnik is None:
        return ''
    if shoda == 'none' or pk != vlastnik:
        return 'Duplicitní telefon v JSON'
    if kontakt is not None and _nesouhlasi(kontakt, data):
        return 'Duplicitní telefon v JSON'
    return ''


def _zarezervuj_telefon_v_davce(telefon_v_davce: dict[str, int], nt_tel: str, pk: int) -> None:
    if nt_tel:
        telefon_v_davce[nt_tel] = pk


@contextmanager
def import_commit_zamek():
    from django.core.cache import cache
    from django.db import connection

    if not cache.add(IMPORT_LOCK_KEY, '1', IMPORT_LOCK_TTL):
        raise ImportZamcenError('Import už probíhá. Počkejte na dokončení.')
    pg_locked = True
    if connection.vendor == 'postgresql':
        with connection.cursor() as cur:
            cur.execute('SELECT pg_try_advisory_lock(%s)', [PG_ADVISORY_LOCK_ID])
            pg_locked = bool(cur.fetchone()[0])
        if not pg_locked:
            cache.delete(IMPORT_LOCK_KEY)
            raise ImportZamcenError('Import už probíhá (databáze).')
    try:
        yield
    finally:
        cache.delete(IMPORT_LOCK_KEY)
        if connection.vendor == 'postgresql' and pg_locked:
            with connection.cursor() as cur:
                cur.execute('SELECT pg_advisory_unlock(%s)', [PG_ADVISORY_LOCK_ID])


def rezervuj_token_potvrzeni(token: str) -> None:
    """Atomicky označí token — druhé potvrzení stejného náhledu selže."""
    from django.core.cache import cache

    klic = f'{IMPORT_TOKEN_PREFIX}{token}'
    if not cache.add(klic, '1', 86400):
        raise ImportTokenPouzitError('Tento náhled už byl potvrzen. Nahrajte JSON znovu.')


def spust_import_commit(payloads: list, *, ulozeny_podpis: dict | None = None) -> ImportReport:
    """Zápis do DB: kontrola podpisu náhledu + commit zámek."""
    with import_commit_zamek():
        kontrola = spust_import(payloads, dry_run=True)
        if ulozeny_podpis is not None and not podpis_souhlasi(ulozeny_podpis, kontrola):
            raise ImportNahledZastaralError(
                'Databáze se od náhledu změnila. Zobrazte nový náhled a teprve potom potvrďte.',
            )
        return spust_import(payloads, dry_run=False)


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


def _zaznam(akce: str, data: dict, *, pk=None, detail: str = '') -> dict:
    return {
        'akce': akce,
        'id': pk or '',
        'jmeno': data.get('jmeno') or '',
        'email': data.get('email') or '',
        'telefon': data.get('_nt_telefon') or '',
        'ico': data.get('_nt_ico') or '',
        'detail': detail,
    }


def spust_import(payloads: list, *, dry_run: bool = True) -> ImportReport:
    report = ImportReport()
    report.pred_pocet = PotencialniKontakt.objects.count()
    stav_pred = _snapshot_stavu()
    by_email, by_phone, by_ico = _index_kontaktu()
    telefon_v_davce: dict[str, int] = {}

    with _import_transakce(dry_run):
        for i, raw in enumerate(payloads, start=1):
            report.nacteno += 1
            try:
                data = normalizuj_radek_partnera(raw)
            except (ValidationError, TypeError, ValueError) as exc:
                report.neplatne.append(f'řádek {i}: {exc}')
                report.zmeny.append(_zaznam('neplatne', {'jmeno': '', 'email': ''}, detail=f'řádek {i}: {exc}'))
                continue

            shoda, pk = najdi_shodu(data, by_email, by_phone, by_ico)
            kontakt_pro_tel = None
            if shoda == 'match' and pk is not None:
                kontakt_pro_tel = PotencialniKontakt.objects.get(pk=pk)
            dup_tel = _kolize_telefonu_v_davce(data, telefon_v_davce, shoda, pk, kontakt_pro_tel)
            if dup_tel:
                report.nejednoznacne += 1
                report.duplicitni_vstup += 1
                if len(report.nejednoznacne_priklady) < 15:
                    report.nejednoznacne_priklady.append(_popis_radku(data))
                report.zmeny.append(_zaznam('konflikt', data, pk=pk, detail=dup_tel))
                continue

            if shoda == 'ambiguous':
                report.nejednoznacne += 1
                if len(report.nejednoznacne_priklady) < 15:
                    report.nejednoznacne_priklady.append(_popis_radku(data))
                report.zmeny.append(_zaznam(
                    'konflikt', data,
                    detail='IČO, telefon nebo e-mail ukazují na víc kontaktů',
                ))
                continue

            if shoda == 'match' and pk is not None:
                report.jednoznacne += 1
                kontakt = kontakt_pro_tel or PotencialniKontakt.objects.get(pk=pk)
                duvod = _nesouhlasi(kontakt, data)
                if duvod:
                    report.nejednoznacne += 1
                    report.jednoznacne -= 1
                    if len(report.nejednoznacne_priklady) < 15:
                        report.nejednoznacne_priklady.append(_popis_radku(data))
                    report.zmeny.append(_zaznam('konflikt', data, pk=kontakt.pk, detail=duvod))
                    continue
                pole = _dopln_prazdna_pole(kontakt, data)
                if pole:
                    report.aktualizovano += 1
                    report.zmeny.append(_zaznam('update', data, pk=kontakt.pk, detail=', '.join(pole)))
                else:
                    report.preskoceno += 1
                    report.zmeny.append(_zaznam('beze_zmeny', data, pk=kontakt.pk))
                _zarezervuj_telefon_v_davce(telefon_v_davce, data['_nt_telefon'], kontakt.pk)
                continue

            if shoda == 'none':
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
                report.zmeny.append(_zaznam('create', data, detail='nový kontakt'))
                _zarezervuj_telefon_v_davce(telefon_v_davce, data['_nt_telefon'], novy.pk)

    stav_po = _snapshot_stavu()
    for kid, stav in stav_pred.items():
        if kid in stav_po and stav_po[kid] != stav:
            report.statusy_zmeneny.append(f'id={kid}: {stav} → {stav_po[kid]}')
    report.po_pocet = PotencialniKontakt.objects.count()
    if dry_run:
        report.po_pocet = report.pred_pocet
    return report