"""Jednorázová kopie presetu do tenant-specific konfigurace. Nikdy nesynchronizuje."""

from django.db import transaction

from archivnik.models import CustomFieldDef, Obor, ObjectType
from archivnik.presets import get_preset


def apply_preset(salon, kod: str) -> dict:
    """
    Zkopíruje katalog do provozovny.

    Idempotentní a never-update: existující obor / typ / pole se nemění
    (název, druh, volby, pořadí). Chybějící typy a pole se doplní podle
    aktuálního katalogu jen pokud obor tohoto presetu ještě neexistuje.

    Opakovaná aplikace stejného presetu (obor se zdroj_preset už je) je no-op
    — i kdyby se mezitím katalog změnil, existující konfigurace zůstane.
    Jiný preset založí další obor.
    """
    catalog = get_preset(kod)
    with transaction.atomic():
        obor = Obor.objects.filter(salon=salon, zdroj_preset=catalog['kod']).first()
        created_obor = False
        if obor is None:
            obor, created_obor = Obor.objects.get_or_create(
                salon=salon,
                nazev=catalog['nazev'],
                defaults={
                    'zdroj_preset': catalog['kod'],
                    'poradi': Obor.objects.filter(salon=salon).count() + 1,
                },
            )
            if not created_obor and not obor.zdroj_preset:
                obor.zdroj_preset = catalog['kod']
                obor.save(update_fields=['zdroj_preset', 'upraveno'])
            elif not created_obor and obor.zdroj_preset != catalog['kod']:
                obor = Obor.objects.create(
                    salon=salon,
                    nazev=f"{catalog['nazev']} ({catalog['kod']})",
                    zdroj_preset=catalog['kod'],
                    poradi=Obor.objects.filter(salon=salon).count() + 1,
                )
                created_obor = True

        created_types = 0
        created_fields = 0
        for index, typ_spec in enumerate(catalog['typy'], start=1):
            typ = ObjectType.objects.filter(salon=salon, nazev=typ_spec['nazev']).first()
            if typ is None:
                typ = ObjectType(
                    salon=salon,
                    obor=obor,
                    nazev=typ_spec['nazev'],
                    poradi=index,
                )
                typ.save()
                created_types += 1
                new_type = True
            else:
                new_type = False
            if not new_type:
                continue
            for field_index, field_spec in enumerate(typ_spec['pole'], start=1):
                pole = CustomFieldDef(
                    salon=salon,
                    typ=typ,
                    nazev=field_spec['nazev'],
                    druh=field_spec['druh'],
                    volby=list(field_spec.get('volby') or []),
                    poradi=field_index,
                )
                pole.save()
                created_fields += 1
        return _snapshot(
            salon, obor,
            created=created_obor or created_types > 0 or created_fields > 0,
            skipped=created_types == 0 and created_fields == 0 and not created_obor,
            created_types=created_types,
            created_fields=created_fields,
        )


def create_obor(salon, nazev: str) -> Obor:
    nazev = (nazev or '').strip()
    if not nazev:
        raise ValueError('Zadejte název oboru.')
    obor = Obor(
        salon=salon,
        nazev=nazev,
        poradi=Obor.objects.filter(salon=salon).count() + 1,
    )
    obor.save()
    return obor


def _snapshot(salon, obor, *, created, skipped, created_types=0, created_fields=0):
    typy = list(ObjectType.objects.filter(salon=salon, obor=obor).order_by('poradi', 'nazev'))
    return {
        'obor': obor,
        'created': created,
        'skipped': skipped,
        'created_types': created_types,
        'created_fields': created_fields,
        'typy_pocet': len(typy),
        'pole_pocet': CustomFieldDef.objects.filter(salon=salon, typ__obor=obor).count(),
    }
