import calendar
from datetime import date
from decimal import Decimal

from django.db import transaction

from rezervace.models import RezervacniNastaveni, SalonAuditLog, Zamestnanec
from salons.models import Salon

from .models import PartnerNastaveni, PlatbaPartnera


@transaction.atomic
def vytvor_noveho_partnera(*, data: dict, actor):
    """
    Založí Salon + PartnerNastaveni + účet Manager (bez Staff/rozvrhu/fotek).
    Volitelně aktivuje FLOW. Vrací (salon, partner, majitel, flow_user|None).
    """
    from rezervace.services.staff_auth import ensure_owner_flow_user

    salon_email = (data.get('email') or data['majitel_email'] or '').strip()
    salon = Salon.objects.create(
        name=data['name'].strip(),
        address=(data.get('address') or '').strip(),
        phone=(data.get('phone') or '').strip(),
        email=salon_email,
    )

    partner = salon.partner_nastaveni
    partner.domena = data.get('domena') or ''
    partner.tarif = (data.get('tarif') or '').strip()
    partner.fakturacni_email = (
        (data.get('fakturacni_email') or '').strip()
        or data['majitel_email']
        or salon_email
    )
    vs = (data.get('variabilni_symbol') or '').strip() or None
    partner.variabilni_symbol = vs
    partner.periodicita = data.get('periodicita') or PartnerNastaveni.PERIODA_MESIC
    partner.castka = data.get('castka') if data.get('castka') is not None else Decimal('0.00')
    partner.dalsi_splatnost = data.get('dalsi_splatnost') or None
    partner.ulov_cislo_uctu = (data.get('ulov_cislo_uctu') or '').strip()
    partner.save()

    RezervacniNastaveni.objects.get_or_create(
        salon=salon,
        defaults={
            'email_odesilatel': salon_email,
            'email_jmeno_odesilatele': salon.name,
        },
    )

    majitel = Zamestnanec(
        salon=salon,
        jmeno='Manager',
        role=Zamestnanec.ROLE_MAJITEL,
        prihlasovaci_jmeno=data['majitel_email'],
        aktivni=True,
        zobrazit_na_webu=False,
        poradi=0,
    )
    majitel.set_password(data['majitel_heslo'])
    majitel.save()

    flow_user = None
    if data.get('aktivovat_flow', True):
        flow_user, _ = ensure_owner_flow_user(salon, email=data['majitel_email'])

    log_superadmin(
        salon,
        actor,
        f'Založen nový partner (salon #{salon.id}).',
        pred=None,
        po={
            'name': salon.name,
            'majitel_email': data['majitel_email'],
            'vs': partner.variabilni_symbol,
            'flow': bool(flow_user),
        },
    )
    return salon, partner, majitel, flow_user


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
def oznac_platbu(salon, user, zaplaceno_dne, prijata_castka=None, poznamka='', faktura_pdf=None):
    nastaveni = PartnerNastaveni.objects.select_for_update().get(salon=salon)
    if not nastaveni.dalsi_splatnost:
        raise ValueError('Nejdříve nastavte datum další splatnosti.')

    splatnost = nastaveni.dalsi_splatnost
    platba = PlatbaPartnera(
        salon=salon,
        splatnost=splatnost,
        zaplaceno_dne=zaplaceno_dne,
        ocekavana_castka=nastaveni.castka,
        prijata_castka=prijata_castka,
        variabilni_symbol=nastaveni.variabilni_symbol or '',
        poznamka=poznamka,
        oznacil=user,
    )
    if faktura_pdf:
        platba.faktura_pdf = faktura_pdf
    platba.save()
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
            'ma_fakturu': bool(faktura_pdf),
        },
    )
    return platba
