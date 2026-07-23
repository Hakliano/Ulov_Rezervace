import calendar
from datetime import date
from decimal import Decimal

from django.db import transaction

from rezervace.models import SalonAuditLog

from .models import PartnerNastaveni, PlatbaPartnera


def posun_splatnost(puvodni, periodicita):
    if periodicita == PartnerNastaveni.PERIODA_ROK:
        try:
            return puvodni.replace(year=puvodni.year + 1)
        except ValueError:
            return puvodni.replace(year=puvodni.year + 1, day=28)

    mesic = puvodni.month + 1
    rok = puvodni.year
    if mesic == 13:
        mesic = 1
        rok += 1
    den = min(puvodni.day, calendar.monthrange(rok, mesic)[1])
    return date(rok, mesic, den)


def log_superadmin(
    salon,
    user,
    popis,
    kategorie='superadmin',
    pred=None,
    po=None,
    objekt_typ='',
    objekt_id=None,
):
    SalonAuditLog.objects.create(
        salon=salon,
        kdo=f'Superadmin: {user.username}'[:100],
        kategorie=kategorie[:50],
        popis=popis,
        objekt_typ=objekt_typ[:50],
        objekt_id=objekt_id,
        data_pred=pred,
        data_po=po,
    )


@transaction.atomic
def oznac_platbu(salon, user, zaplaceno_dne, prijata_castka=None, poznamka=''):
    nastaveni = PartnerNastaveni.objects.select_for_update().get(salon=salon)
    if not nastaveni.dalsi_splatnost:
        raise ValueError('Nejdříve nastavte datum další splatnosti.')

    splatnost = nastaveni.dalsi_splatnost
    platba = PlatbaPartnera.objects.create(
        salon=salon,
        splatnost=splatnost,
        zaplaceno_dne=zaplaceno_dne,
        ocekavana_castka=nastaveni.castka,
        prijata_castka=prijata_castka,
        variabilni_symbol=nastaveni.variabilni_symbol or '',
        poznamka=poznamka,
        oznacil=user,
    )
    nastaveni.dalsi_splatnost = posun_splatnost(splatnost, nastaveni.periodicita)
    nastaveni.save(update_fields=['dalsi_splatnost', 'aktualizovano'])
    log_superadmin(
        salon,
        user,
        f'Platba se splatností {splatnost:%d.%m.%Y} označena jako zaplacená.',
        kategorie='platby',
        po={
            'zaplaceno_dne': zaplaceno_dne.isoformat(),
            'prijata_castka': str(prijata_castka if prijata_castka is not None else Decimal('0')),
            'dalsi_splatnost': nastaveni.dalsi_splatnost.isoformat(),
        },
    )
    return platba
