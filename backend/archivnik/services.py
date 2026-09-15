"""Jednorázová kopie presetu do tenant-specific konfigurace. Nikdy nesynchronizuje."""

from django.db import transaction

from archivnik.models import CustomFieldDef, Obor, ObjectType
from archivnik.presets import get_preset


def salon_is_onboarded(salon) -> bool:
    return (
        Obor.objects.filter(salon=salon).exists()
        or ObjectType.objects.filter(salon=salon).exists()
    )


def salon_config_status(salon) -> dict:
    onboarded = salon_is_onboarded(salon)
    obor = Obor.objects.filter(salon=salon).order_by('poradi', 'id').first()
    return {
        'onboarded': onboarded,
        'muze_aplikovat_preset': not onboarded,
        'objekt_jednotne': obor.objekt_jednotne if obor else 'Objekt',
        'objekt_mnozne': obor.objekt_mnozne if obor else 'Objekty',
    }


def apply_preset(salon, kod: str) -> dict:
    """
    Zkopíruje katalog do provozovny.

    Idempotentní a never-update: existující obor / typ / pole se nemění
    (název, druh, volby, pořadí). Chybějící typy a pole se doplní podle
    aktuálního katalogu jen pokud obor tohoto presetu ještě neexistuje.

    Opakovaná aplikace stejného presetu (obor se zdroj_preset už je) je no-op
    — i kdyby se mezitím katalog změnil, existující konfigurace zůstane.
    Jiný preset založí další obor.

    Partner API smí apply volat jen u prázdné provozovny (onboarding).
    Přímé volání služby zůstává pro seed a budoucí Partner-admin (P4).
    """
    catalog = get_preset(kod)
    with transaction.atomic():
        obor = Obor.objects.filter(salon=salon, zdroj_preset=catalog['kod']).first()
        created_obor = False
        defaults = {
            'zdroj_preset': catalog['kod'],
            'poradi': Obor.objects.filter(salon=salon).count() + 1,
            'objekt_jednotne': catalog.get('objekt_jednotne') or 'Objekt',
            'objekt_mnozne': catalog.get('objekt_mnozne') or 'Objekty',
        }
        if obor is None:
            obor, created_obor = Obor.objects.get_or_create(
                salon=salon,
                nazev=catalog['nazev'],
                defaults=defaults,
            )
            if not created_obor and not obor.zdroj_preset:
                obor.zdroj_preset = catalog['kod']
                if obor.objekt_jednotne == 'Objekt':
                    obor.objekt_jednotne = defaults['objekt_jednotne']
                    obor.objekt_mnozne = defaults['objekt_mnozne']
                obor.save(update_fields=[
                    'zdroj_preset', 'objekt_jednotne', 'objekt_mnozne', 'upraveno',
                ])
            elif not created_obor and obor.zdroj_preset != catalog['kod']:
                obor = Obor.objects.create(
                    salon=salon,
                    nazev=f"{catalog['nazev']} ({catalog['kod']})",
                    **defaults,
                )
                created_obor = True

        created_types = 0
        created_fields = 0
        kod = catalog['kod']
        for index, typ_spec in enumerate(catalog['typy'], start=1):
            typ = ObjectType.objects.filter(salon=salon, nazev=typ_spec['nazev']).first()
            if typ is None:
                typ = ObjectType(
                    salon=salon,
                    obor=obor,
                    nazev=typ_spec['nazev'],
                    poradi=index,
                    vyzaduje_nazev=typ_spec.get('vyzaduje_nazev', True),
                    zdroj_preset=kod,
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
                    zdroj_preset=kod,
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


def create_obor(salon, nazev: str, objekt_jednotne='Objekt', objekt_mnozne='Objekty') -> Obor:
    nazev = (nazev or '').strip()
    if not nazev:
        raise ValueError('Zadejte název oboru.')
    jednotne = (objekt_jednotne or '').strip() or 'Objekt'
    mnozne = (objekt_mnozne or '').strip() or 'Objekty'
    obor = Obor(
        salon=salon,
        nazev=nazev,
        poradi=Obor.objects.filter(salon=salon).count() + 1,
        objekt_jednotne=jednotne[:40],
        objekt_mnozne=mnozne[:40],
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
