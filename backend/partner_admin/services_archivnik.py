"""Superadmin konfigurace Archivníka v Partner-adminu (P4.3)."""

from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, Prefetch, ProtectedError, Q
from django.utils import timezone

from archivnik.models import (
    CustomFieldDef,
    CustomFieldValue,
    FieldKind,
    Obor,
    Object,
    ObjectType,
)
from archivnik.services import create_obor as vytvor_obor_core
from archivnik.services import primary_obor
from partner_admin.models import MODUL_ARCHIVNIK
from partner_admin.services import log_superadmin
from partner_admin.services_moduly import partner_modul
from rezervace.models import Zamestnanec


class ArchivnikSpravaError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(message)


def _sklonuj(n, jeden, dva, pet):
    n = abs(int(n))
    if n == 1:
        form = jeden
    elif 2 <= n <= 4:
        form = dva
    else:
        form = pet
    return f'{n} {form}'


def _int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def obor_delete_blockers(salon, obor):
    if obor.salon_id != salon.id:
        return ['Obor nepatří této provozovně.']
    aktualni = primary_obor(salon)
    if aktualni and aktualni.id == obor.id:
        return [
            f'Nelze smazat aktuální Obor {obor.nazev}. '
            'Nejdřív nastavte jiný jako aktuální.'
        ]
    n = Object.objects.filter(salon=salon, typ__obor=obor).count()
    if n:
        return [
            f'Nelze smazat Obor {obor.nazev} – používá jej '
            f'{_sklonuj(n, "objekt", "objekty", "objektů")}.'
        ]
    return []


def typ_delete_blockers(salon, typ):
    if typ.salon_id != salon.id:
        return ['Typ nepatří této provozovně.']
    n = Object.objects.filter(salon=salon, typ=typ).count()
    if n:
        return [
            f'Nelze smazat typ {typ.nazev} – používá jej '
            f'{_sklonuj(n, "objekt", "objekty", "objektů")}.'
        ]
    return []


def pole_delete_blockers(salon, pole):
    if pole.salon_id != salon.id:
        return ['Pole nepatří této provozovně.']
    n = CustomFieldValue.objects.filter(pole=pole, objekt__salon=salon).count()
    if n:
        return [
            f'Nelze smazat pole {pole.nazev} – obsahuje '
            f'{_sklonuj(n, "uloženou hodnotu", "uložené hodnoty", "uložených hodnot")}.'
        ]
    return []


def _priloz_smazani(row, blockers):
    row.muze_smazat = not blockers
    row.smazat_duvod = blockers[0] if blockers else ''
    return row


def archivnik_sprava_data(salon):
    """Tenant-scoped snapshot konfigurace včetně blockerů mazání."""
    modul = partner_modul(salon, MODUL_ARCHIVNIK)
    aktualni = primary_obor(salon)
    pole_qs = (
        CustomFieldDef.objects.filter(salon=salon)
        .annotate(hodnoty_pocet=Count('hodnoty'))
        .order_by('poradi', 'id')
    )
    typy = list(
        ObjectType.objects.filter(salon=salon)
        .select_related('obor')
        .prefetch_related(Prefetch('pole', queryset=pole_qs))
        .annotate(objekty_pocet=Count('objekty', distinct=True))
        .order_by('poradi', 'nazev', 'id')
    )
    typy_podle_oboru = {}
    typy_bez_oboru = []
    for typ in typy:
        _priloz_smazani(typ, typ_delete_blockers(salon, typ))
        for pole in typ.pole.all():
            _priloz_smazani(pole, pole_delete_blockers(salon, pole))
        if typ.obor_id is None:
            typy_bez_oboru.append(typ)
        else:
            typy_podle_oboru.setdefault(typ.obor_id, []).append(typ)

    obory = []
    for obor in Obor.objects.filter(salon=salon).annotate(
        objekty_pocet=Count('typy__objekty', distinct=True),
    ).order_by('poradi', 'id'):
        _priloz_smazani(obor, obor_delete_blockers(salon, obor))
        obory.append({
            'obor': obor,
            'aktualni': bool(aktualni and obor.id == aktualni.id),
            'typy': typy_podle_oboru.get(obor.id, []),
        })

    ted = timezone.now()
    session_counts = dict(
        Zamestnanec.objects.filter(salon=salon).annotate(
            n=Count(
                'archivnik_sessiony',
                filter=Q(archivnik_sessiony__expirace__gt=ted),
            )
        ).values_list('id', 'n')
    )
    zamestnanci = []
    for z in Zamestnanec.objects.filter(salon=salon).order_by('role', 'poradi', 'id'):
        zamestnanci.append({
            'zamestnanec': z,
            'ma_prihlaseni': z.ma_prihlaseni,
            'session_pocet': session_counts.get(z.id, 0) if z.aktivni else 0,
        })
    return {
        'modul': modul,
        'modul_aktivni': bool(modul and modul.je_aktivni),
        'aktualni_obor': aktualni,
        'obory': obory,
        'typy_bez_oboru': typy_bez_oboru,
        'zamestnanci': zamestnanci,
        'field_kinds': FieldKind.choices,
        'vsechny_obory': [row['obor'] for row in obory],
    }


def _obor(salon, obor_id):
    try:
        return Obor.objects.get(pk=obor_id, salon=salon)
    except (Obor.DoesNotExist, TypeError, ValueError) as exc:
        raise ArchivnikSpravaError('Obor v této provozovně neexistuje.') from exc


def _typ(salon, typ_id):
    try:
        return ObjectType.objects.get(pk=typ_id, salon=salon)
    except (ObjectType.DoesNotExist, TypeError, ValueError) as exc:
        raise ArchivnikSpravaError('Typ v této provozovně neexistuje.') from exc


def _pole(salon, pole_id):
    try:
        return CustomFieldDef.objects.select_related('typ').get(pk=pole_id, salon=salon)
    except (CustomFieldDef.DoesNotExist, TypeError, ValueError) as exc:
        raise ArchivnikSpravaError('Pole v této provozovně neexistuje.') from exc


def _volby_z_textu(raw):
    if isinstance(raw, list):
        return [str(v).strip() for v in raw if str(v).strip()]
    text = raw or ''
    return [line.strip() for line in str(text).splitlines() if line.strip()]


def vytvor_obor(salon, actor, *, nazev, objekt_jednotne, objekt_mnozne):
    try:
        obor = vytvor_obor_core(salon, nazev, objekt_jednotne, objekt_mnozne)
    except ValueError as exc:
        raise ArchivnikSpravaError(str(exc)) from exc
    except IntegrityError as exc:
        raise ArchivnikSpravaError('Obor s tímto názvem už v provozovně existuje.') from exc
    except ValidationError as exc:
        raise ArchivnikSpravaError(_validation_text(exc)) from exc
    log_superadmin(
        salon, actor, f'Archivník: vytvořen Obor {obor.nazev}',
        kategorie='archivnik', objekt_typ='archivnik.Obor', objekt_id=obor.id,
        po={'nazev': obor.nazev, 'aktualni': obor.aktualni},
    )
    return obor


def uloz_obor(salon, actor, obor_id, *, nazev, objekt_jednotne, objekt_mnozne):
    obor = _obor(salon, obor_id)
    pred = {
        'nazev': obor.nazev,
        'objekt_jednotne': obor.objekt_jednotne,
        'objekt_mnozne': obor.objekt_mnozne,
    }
    obor.nazev = (nazev or '').strip()
    obor.objekt_jednotne = ((objekt_jednotne or '').strip() or 'Objekt')[:40]
    obor.objekt_mnozne = ((objekt_mnozne or '').strip() or 'Objekty')[:40]
    if not obor.nazev:
        raise ArchivnikSpravaError('Zadejte název Oboru.')
    try:
        obor.save()
    except IntegrityError as exc:
        raise ArchivnikSpravaError('Obor s tímto názvem už v provozovně existuje.') from exc
    except ValidationError as exc:
        raise ArchivnikSpravaError(_validation_text(exc)) from exc
    log_superadmin(
        salon, actor, f'Archivník: upraven Obor {obor.nazev}',
        kategorie='archivnik', objekt_typ='archivnik.Obor', objekt_id=obor.id,
        pred=pred,
        po={
            'nazev': obor.nazev,
            'objekt_jednotne': obor.objekt_jednotne,
            'objekt_mnozne': obor.objekt_mnozne,
        },
    )
    return obor


@transaction.atomic
def nastav_aktualni_obor(salon, actor, obor_id):
    obor = Obor.objects.select_for_update().get(pk=_obor(salon, obor_id).pk)
    Obor.objects.filter(salon=salon, aktualni=True).exclude(pk=obor.pk).update(aktualni=False)
    if not obor.aktualni:
        obor.aktualni = True
        obor.save(update_fields=['aktualni', 'upraveno'])
    log_superadmin(
        salon, actor, f'Archivník: aktuální Obor {obor.nazev}',
        kategorie='archivnik', objekt_typ='archivnik.Obor', objekt_id=obor.id,
        po={'aktualni': True},
    )
    return obor


@transaction.atomic
def smaz_obor(salon, actor, obor_id, *, potvrzeno):
    obor = _obor(salon, obor_id)
    blockers = obor_delete_blockers(salon, obor)
    if blockers:
        raise ArchivnikSpravaError(blockers[0])
    if not potvrzeno:
        raise ArchivnikSpravaError('Smazání Oboru nebylo potvrzeno.')
    if Object.objects.filter(salon=salon, typ__obor=obor).exists():
        raise ArchivnikSpravaError(
            f'Nelze smazat Obor {obor.nazev} – používá jej provozní data.'
        )
    nazev = obor.nazev
    obor_pk = obor.id
    typy_ids = list(ObjectType.objects.filter(salon=salon, obor=obor).values_list('id', flat=True))
    CustomFieldDef.objects.filter(salon=salon, typ_id__in=typy_ids).delete()
    try:
        ObjectType.objects.filter(salon=salon, id__in=typy_ids).delete()
    except ProtectedError as exc:
        raise ArchivnikSpravaError(
            f'Nelze smazat Obor {nazev} – některý typ má objekty.'
        ) from exc
    obor.delete()
    log_superadmin(
        salon, actor, f'Archivník: smazán Obor {nazev}',
        kategorie='archivnik', objekt_typ='archivnik.Obor', objekt_id=obor_pk,
        pred={'nazev': nazev, 'typy_id': typy_ids},
    )


def vytvor_typ(salon, actor, *, nazev, obor_id, poradi, aktivni, vyzaduje_nazev):
    nazev = (nazev or '').strip()
    if not nazev:
        raise ArchivnikSpravaError('Zadejte název typu.')
    obor = _obor(salon, obor_id) if obor_id not in (None, '', '0') else None
    if obor_id not in (None, '', '0') and obor is None:
        raise ArchivnikSpravaError('Obor v této provozovně neexistuje.')
    typ = ObjectType(
        salon=salon,
        obor=obor,
        nazev=nazev,
        poradi=_int(poradi, (obor.typy.count() + 1) if obor else ObjectType.objects.filter(salon=salon).count() + 1),
        aktivni=bool(aktivni),
        vyzaduje_nazev=bool(vyzaduje_nazev),
    )
    try:
        typ.save()
    except IntegrityError as exc:
        raise ArchivnikSpravaError('Typ s tímto názvem už v provozovně existuje.') from exc
    except ValidationError as exc:
        raise ArchivnikSpravaError(_validation_text(exc)) from exc
    log_superadmin(
        salon, actor, f'Archivník: vytvořen typ {typ.nazev}',
        kategorie='archivnik', objekt_typ='archivnik.ObjectType', objekt_id=typ.id,
        po={'nazev': typ.nazev, 'obor_id': typ.obor_id, 'aktivni': typ.aktivni},
    )
    return typ


def uloz_typ(salon, actor, typ_id, *, nazev, obor_id, poradi, aktivni, vyzaduje_nazev):
    typ = _typ(salon, typ_id)
    pred = {
        'nazev': typ.nazev,
        'obor_id': typ.obor_id,
        'poradi': typ.poradi,
        'aktivni': typ.aktivni,
        'vyzaduje_nazev': typ.vyzaduje_nazev,
    }
    nazev = (nazev or '').strip()
    if not nazev:
        raise ArchivnikSpravaError('Zadejte název typu.')
    obor = _obor(salon, obor_id) if obor_id not in (None, '', '0') else None
    typ.nazev = nazev
    typ.obor = obor
    typ.poradi = _int(poradi, typ.poradi)
    typ.aktivni = bool(aktivni)
    typ.vyzaduje_nazev = bool(vyzaduje_nazev)
    try:
        typ.save()
    except IntegrityError as exc:
        raise ArchivnikSpravaError('Typ s tímto názvem už v provozovně existuje.') from exc
    except ValidationError as exc:
        raise ArchivnikSpravaError(_validation_text(exc)) from exc
    log_superadmin(
        salon, actor, f'Archivník: upraven typ {typ.nazev}',
        kategorie='archivnik', objekt_typ='archivnik.ObjectType', objekt_id=typ.id,
        pred=pred,
        po={
            'nazev': typ.nazev,
            'obor_id': typ.obor_id,
            'poradi': typ.poradi,
            'aktivni': typ.aktivni,
            'vyzaduje_nazev': typ.vyzaduje_nazev,
        },
    )
    return typ


def nastav_typ_aktivni(salon, actor, typ_id, *, aktivni):
    typ = _typ(salon, typ_id)
    pred = typ.aktivni
    typ.aktivni = bool(aktivni)
    typ.save(update_fields=['aktivni', 'upraveno'])
    stav = 'aktivován' if typ.aktivni else 'deaktivován'
    log_superadmin(
        salon, actor, f'Archivník: typ {typ.nazev} {stav}',
        kategorie='archivnik', objekt_typ='archivnik.ObjectType', objekt_id=typ.id,
        pred={'aktivni': pred}, po={'aktivni': typ.aktivni},
    )
    return typ


@transaction.atomic
def smaz_typ(salon, actor, typ_id, *, potvrzeno):
    typ = _typ(salon, typ_id)
    blockers = typ_delete_blockers(salon, typ)
    if blockers:
        raise ArchivnikSpravaError(blockers[0])
    if not potvrzeno:
        raise ArchivnikSpravaError('Smazání typu nebylo potvrzeno.')
    if Object.objects.filter(salon=salon, typ=typ).exists():
        raise ArchivnikSpravaError(
            f'Nelze smazat typ {typ.nazev} – používá jej provozní data.'
        )
    nazev = typ.nazev
    typ_pk = typ.id
    CustomFieldDef.objects.filter(salon=salon, typ=typ).delete()
    try:
        typ.delete()
    except ProtectedError as exc:
        raise ArchivnikSpravaError(
            f'Nelze smazat typ {nazev} – používá jej provozní data.'
        ) from exc
    log_superadmin(
        salon, actor, f'Archivník: smazán typ {nazev}',
        kategorie='archivnik', objekt_typ='archivnik.ObjectType', objekt_id=typ_pk,
        pred={'nazev': nazev},
    )


def vytvor_pole(salon, actor, *, typ_id, nazev, druh, volby, poradi, aktivni):
    typ = _typ(salon, typ_id)
    nazev = (nazev or '').strip()
    if not nazev:
        raise ArchivnikSpravaError('Zadejte název pole.')
    pole = CustomFieldDef(
        salon=salon,
        typ=typ,
        nazev=nazev,
        druh=(druh or FieldKind.TEXT).strip(),
        volby=_volby_z_textu(volby),
        poradi=_int(poradi, typ.pole.count() + 1),
        aktivni=bool(aktivni),
    )
    try:
        pole.save()
    except IntegrityError as exc:
        raise ArchivnikSpravaError('Pole s tímto názvem u typu už existuje.') from exc
    except ValidationError as exc:
        raise ArchivnikSpravaError(_validation_text(exc)) from exc
    log_superadmin(
        salon, actor, f'Archivník: vytvořeno pole {pole.nazev}',
        kategorie='archivnik', objekt_typ='archivnik.CustomFieldDef', objekt_id=pole.id,
        po={'nazev': pole.nazev, 'druh': pole.druh, 'typ_id': typ.id},
    )
    return pole


def uloz_pole(salon, actor, pole_id, *, nazev, druh, volby, poradi, aktivni):
    pole = _pole(salon, pole_id)
    pred = {
        'nazev': pole.nazev,
        'druh': pole.druh,
        'volby': list(pole.volby or []),
        'poradi': pole.poradi,
        'aktivni': pole.aktivni,
    }
    nazev = (nazev or '').strip()
    if not nazev:
        raise ArchivnikSpravaError('Zadejte název pole.')
    novy_druh = (druh or pole.druh).strip()
    nove_volby = _volby_z_textu(volby) if novy_druh == FieldKind.VYBER else []
    hodnoty_qs = CustomFieldValue.objects.filter(pole=pole, objekt__salon=salon)
    if hodnoty_qs.exists() and novy_druh != pole.druh:
        raise ArchivnikSpravaError(
            f'Nelze změnit druh pole {pole.nazev} – obsahuje '
            f'{_sklonuj(hodnoty_qs.count(), "uloženou hodnotu", "uložené hodnoty", "uložených hodnot")}.'
        )
    if pole.druh == FieldKind.VYBER and novy_druh == FieldKind.VYBER:
        pouzite = set(
            hodnoty_qs.exclude(hodnota='').values_list('hodnota', flat=True)
        )
        odebrane = set(pole.volby or []) - set(nove_volby)
        kolize = sorted(pouzite & odebrane)
        if kolize:
            raise ArchivnikSpravaError(
                f'Nelze odebrat volbu {kolize[0]} u pole {pole.nazev} – je uložená u objektů.'
            )
    pole.nazev = nazev
    pole.druh = novy_druh
    pole.volby = nove_volby
    pole.poradi = _int(poradi, pole.poradi)
    pole.aktivni = bool(aktivni)
    try:
        pole.save()
    except IntegrityError as exc:
        raise ArchivnikSpravaError('Pole s tímto názvem u typu už existuje.') from exc
    except ValidationError as exc:
        raise ArchivnikSpravaError(_validation_text(exc)) from exc
    log_superadmin(
        salon, actor, f'Archivník: upraveno pole {pole.nazev}',
        kategorie='archivnik', objekt_typ='archivnik.CustomFieldDef', objekt_id=pole.id,
        pred=pred,
        po={
            'nazev': pole.nazev,
            'druh': pole.druh,
            'volby': list(pole.volby or []),
            'poradi': pole.poradi,
            'aktivni': pole.aktivni,
        },
    )
    return pole


def nastav_pole_aktivni(salon, actor, pole_id, *, aktivni):
    pole = _pole(salon, pole_id)
    pred = pole.aktivni
    pole.aktivni = bool(aktivni)
    pole.save(update_fields=['aktivni'])
    stav = 'aktivováno' if pole.aktivni else 'deaktivováno'
    log_superadmin(
        salon, actor, f'Archivník: pole {pole.nazev} {stav}',
        kategorie='archivnik', objekt_typ='archivnik.CustomFieldDef', objekt_id=pole.id,
        pred={'aktivni': pred}, po={'aktivni': pole.aktivni},
    )
    return pole


@transaction.atomic
def smaz_pole(salon, actor, pole_id, *, potvrzeno):
    pole = _pole(salon, pole_id)
    blockers = pole_delete_blockers(salon, pole)
    if blockers:
        raise ArchivnikSpravaError(blockers[0])
    if not potvrzeno:
        raise ArchivnikSpravaError('Smazání pole nebylo potvrzeno.')
    if CustomFieldValue.objects.filter(pole=pole, objekt__salon=salon).exists():
        raise ArchivnikSpravaError(
            f'Nelze smazat pole {pole.nazev} – obsahuje uložené hodnoty.'
        )
    nazev = pole.nazev
    pole_pk = pole.id
    pole.delete()
    log_superadmin(
        salon, actor, f'Archivník: smazáno pole {nazev}',
        kategorie='archivnik', objekt_typ='archivnik.CustomFieldDef', objekt_id=pole_pk,
        pred={'nazev': nazev},
    )


def _validation_text(exc):
    if hasattr(exc, 'message_dict'):
        parts = []
        for msgs in exc.message_dict.values():
            parts.extend(str(m) for m in msgs)
        return '; '.join(parts) or 'Neplatná data.'
    if getattr(exc, 'messages', None):
        return '; '.join(str(m) for m in exc.messages)
    return str(exc)
