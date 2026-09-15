"""Read-only přehled konfigurace Archivníka pro Partner-admin (P4.2)."""

from django.db.models import Count, Prefetch, Q
from django.utils import timezone

from archivnik.models import CustomFieldDef, Obor, ObjectType
from archivnik.services import primary_obor
from partner_admin.models import MODUL_ARCHIVNIK
from partner_admin.services_moduly import partner_modul
from rezervace.models import Zamestnanec


def archivnik_sprava_data(salon):
    """Tenant-scoped snapshot. Žádný zápis do konfigurace."""
    modul = partner_modul(salon, MODUL_ARCHIVNIK)
    aktualni = primary_obor(salon)
    typy = list(
        ObjectType.objects.filter(salon=salon)
        .select_related('obor')
        .prefetch_related(
            Prefetch(
                'pole',
                queryset=CustomFieldDef.objects.filter(salon=salon).order_by('poradi', 'id'),
            )
        )
        .order_by('poradi', 'nazev', 'id')
    )
    typy_podle_oboru = {}
    typy_bez_oboru = []
    for typ in typy:
        if typ.obor_id is None:
            typy_bez_oboru.append(typ)
        else:
            typy_podle_oboru.setdefault(typ.obor_id, []).append(typ)

    obory = []
    for obor in Obor.objects.filter(salon=salon).order_by('poradi', 'id'):
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
    }
