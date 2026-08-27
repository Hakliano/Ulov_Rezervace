import calendar
from datetime import date
from decimal import Decimal

from django.db import connection, transaction
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from rezervace.models import RezervacniNastaveni, SalonAuditLog, Zamestnanec
from salons.models import Salon

from .models import (
    KamProvize,
    PartnerNastaveni,
    PlatbaPartnera,
    UlovCisloUctu,
    vychozi_variabilni_symbol,
)


def _sync_salon_id_sequence():
    """Po seedech s pk=… musí Postgres sequence dohnat MAX(id)."""
    if connection.vendor != 'postgresql':
        return
    with connection.cursor() as c:
        c.execute(
            """
            SELECT setval(
              pg_get_serial_sequence('salons_salon', 'id'),
              COALESCE((SELECT MAX(id) FROM salons_salon), 1),
              true
            )
            """
        )


@transaction.atomic
def vytvor_noveho_partnera(*, data: dict, actor):
    """
    Založí Salon + PartnerNastaveni + účet Manager (bez Staff/rozvrhu/fotek).
    Volitelně aktivuje FLOW. Vrací (salon, partner, majitel, flow_user|None).
    """
    from rezervace.services.staff_auth import ensure_owner_flow_user

    _sync_salon_id_sequence()

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
    vs = (data.get('variabilni_symbol') or '').strip()
    partner.variabilni_symbol = vs or vychozi_variabilni_symbol(salon.id) or None
    partner.periodicita = data.get('periodicita') or PartnerNastaveni.PERIODA_MESIC
    partner.castka = data.get('castka') if data.get('castka') is not None else Decimal('0.00')
    partner.dalsi_splatnost = data.get('dalsi_splatnost') or None
    partner.kam = data.get('kam') or None
    partner.je_testovaci = bool(data.get('je_testovaci'))
    partner.prvni_platba = data.get('prvni_platba') if data.get('prvni_platba') is not None else Decimal('0.00')
    partner.kam_provize = data.get('kam_provize') if data.get('kam_provize') is not None else Decimal('0.00')
    partner.kam_procento = data.get('kam_procento') if data.get('kam_procento') is not None else Decimal('0.00')
    partner.ico = (data.get('ico') or '').strip()
    partner.ulov_cislo_uctu = primarni_ulov_ucet()
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

    if data.get('aktivovat_materialnik'):
        from .services_moduly import nastav_modul
        nastav_modul(salon, 'materialnik', True, actor)

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


def nastav_vychozi_variabilni_symboly():
    """Všem partnerům nastaví VS 80+ID. Přepíše stávající hodnoty."""
    PartnerNastaveni.objects.update(variabilni_symbol=None)
    for partner in PartnerNastaveni.objects.all().iterator():
        partner.variabilni_symbol = vychozi_variabilni_symbol(partner.salon_id) or None
        partner.save(update_fields=['variabilni_symbol', 'aktualizovano'])


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
    je_prvni = not PlatbaPartnera.objects.filter(salon=salon).exists()
    ocekavana = nastaveni.castka
    if je_prvni and nastaveni.prvni_platba and nastaveni.prvni_platba > 0:
        ocekavana = nastaveni.prvni_platba
    platba = PlatbaPartnera(
        salon=salon,
        splatnost=splatnost,
        zaplaceno_dne=zaplaceno_dne,
        ocekavana_castka=ocekavana,
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
    uvolni_kam_provizi(platba)
    if not platba.faktura_pdf:
        try:
            from .faktura import zajisti_fakturu
            zajisti_fakturu(platba)
            platba.refresh_from_db()
        except Exception as exc:
            log_superadmin(
                salon,
                user,
                f'Platba uložena, ale fakturu se nepodařilo vygenerovat: {exc}'[:400],
                kategorie='platby',
            )
    log_superadmin(
        salon,
        user,
        f'Platba se splatností {splatnost:%d.%m.%Y} označena jako zaplacená.',
        kategorie='platby',
        po={
            'zaplaceno_dne': zaplaceno_dne.isoformat(),
            'prijata_castka': str(prijata_castka if prijata_castka is not None else Decimal('0')),
            'dalsi_splatnost': nastaveni.dalsi_splatnost.isoformat(),
            'ma_fakturu': bool(platba.faktura_pdf),
            'cislo_faktury': platba.cislo_faktury or '',
        },
    )
    return platba


def seznam_ulov_uctu():
    return list(UlovCisloUctu.objects.filter(aktivni=True).order_by('-primarni', 'razeni', 'id'))


def primarni_ulov_ucet():
    row = (
        UlovCisloUctu.objects.filter(aktivni=True)
        .order_by('-primarni', 'razeni', 'id')
        .first()
    )
    return (row.cislo if row else '').strip()


def synchronizuj_ulov_ucty():
    """Jedno místo pravdy → stejný primární účet na všech salonech (QR ve FLOW)."""
    cislo = primarni_ulov_ucet()
    PartnerNastaveni.objects.update(ulov_cislo_uctu=cislo)
    return cislo


def vygeneruj_demo_heslo(delka=12):
    import re
    from rezervace.services.emails import generate_heslo

    for _ in range(30):
        heslo = generate_heslo(delka)
        if re.search(r'[A-Za-z]', heslo) and re.search(r'\d', heslo):
            return heslo
    return generate_heslo(10) + 'A1'


def resetuj_heslo_majitele(majitel, nove, actor):
    """Sdílené heslo web + FLOW, zruší relace. Vrací e-mail loginu."""
    from flow.auth import zrusit_vsechny_sessiony as zrusit_flow_sessiony
    from flow.models import FlowUser
    from rezervace.services.staff_auth import sync_owner_heslo_do_flow

    majitel.set_password(nove)
    majitel.save(update_fields=['password_hash'])
    majitel.sessiony.all().delete()
    sync_owner_heslo_do_flow(majitel, nove)
    try:
        zrusit_flow_sessiony(majitel.flow_ucet)
    except FlowUser.DoesNotExist:
        pass
    log_superadmin(
        majitel.salon,
        actor,
        f'Resetováno heslo účtu {majitel.prihlasovaci_jmeno}; všechny relace zrušeny.',
        kategorie='ucty',
        objekt_typ='Zamestnanec',
        objekt_id=majitel.id,
    )
    return majitel.prihlasovaci_jmeno


def uvolni_kam_provizi(platba):
    """Po první označené platbě a provizi > 0 vznikne dluh KAM. Jen jednou."""
    salon = platba.salon
    try:
        nastaveni = salon.partner_nastaveni
    except PartnerNastaveni.DoesNotExist:
        return None
    if not nastaveni.kam_id:
        return None
    if not nastaveni.kam_provize or nastaveni.kam_provize <= 0:
        return None
    if KamProvize.objects.filter(salon=salon, typ=KamProvize.TYP_PRVNI).exists():
        return None
    if PlatbaPartnera.objects.filter(salon=salon).count() != 1:
        return None
    prijata = platba.prijata_castka if platba.prijata_castka is not None else platba.ocekavana_castka
    return KamProvize.objects.create(
        kam=nastaveni.kam,
        salon=salon,
        platba=platba,
        typ=KamProvize.TYP_PRVNI,
        obdobi=platba.zaplaceno_dne.replace(day=1),
        castka=nastaveni.kam_provize,
        prvni_platba=prijata or Decimal('0.00'),
        uvolneno_dne=platba.zaplaceno_dne,
        poznamka='První platba',
    )


def _obdobi(den):
    return den.replace(day=1)


def kam_procento_za_mesic(kam, od_dne, do_dne):
    """Živé % z přijatých plateb po první platbě, ještě nesečtené do KamProvize."""
    celkem = Decimal('0.00')
    radky = []
    obdobi = od_dne.replace(day=1)
    uz_ulozeno = set(
        KamProvize.objects.filter(
            kam=kam,
            typ=KamProvize.TYP_PROCENTO,
            obdobi=obdobi,
        ).values_list('salon_id', flat=True)
    )
    for nast in PartnerNastaveni.objects.filter(kam=kam, kam_procento__gt=0).select_related('salon'):
        if nast.salon_id in uz_ulozeno:
            continue
        prvni_id = (
            PlatbaPartnera.objects.filter(salon=nast.salon)
            .order_by('zaplaceno_dne', 'id')
            .values_list('id', flat=True)
            .first()
        )
        qs = PlatbaPartnera.objects.filter(
            salon=nast.salon,
            zaplaceno_dne__gte=od_dne,
            zaplaceno_dne__lte=do_dne,
        )
        if prvni_id:
            qs = qs.exclude(pk=prvni_id)
        prijate = qs.aggregate(s=Sum(Coalesce('prijata_castka', 'ocekavana_castka')))['s'] or Decimal('0.00')
        if prijate <= 0:
            continue
        castka = (prijate * nast.kam_procento / Decimal('100')).quantize(Decimal('0.01'))
        if castka <= 0:
            continue
        celkem += castka
        radky.append({
            'salon': nast.salon,
            'castka': castka,
            'zaklad': prijate,
            'procento': nast.kam_procento,
        })
    return celkem, radky


def kam_vydelal_mesic(kam, dnes=None):
    """Provize za kalendářní měsíc (uložené i živé %)."""
    from calendar import monthrange

    dnes = dnes or timezone.localdate()
    zacatek = _obdobi(dnes)
    konec = dnes.replace(day=monthrange(dnes.year, dnes.month)[1])
    ulozene = (
        KamProvize.objects.filter(kam=kam, obdobi=zacatek).aggregate(s=Sum('castka'))['s']
        or Decimal('0.00')
    )
    procenta, _ = kam_procento_za_mesic(kam, zacatek, konec)
    return ulozene + procenta


def kam_vydelal_celkem(kam, dnes=None):
    dnes = dnes or timezone.localdate()
    ulozene = KamProvize.objects.filter(kam=kam).aggregate(s=Sum('castka'))['s'] or Decimal('0.00')
    from calendar import monthrange
    zacatek = _obdobi(dnes)
    konec = dnes.replace(day=monthrange(dnes.year, dnes.month)[1])
    procenta, _ = kam_procento_za_mesic(kam, zacatek, konec)
    return ulozene + procenta


def kam_dluh_mesic(kam, dnes=None):
    from calendar import monthrange

    dnes = dnes or timezone.localdate()
    zacatek = _obdobi(dnes)
    konec = dnes.replace(day=monthrange(dnes.year, dnes.month)[1])
    uvolnene = KamProvize.objects.filter(
        kam=kam,
        stav=KamProvize.STAV_K_VYPLATE,
        obdobi=zacatek,
    ).aggregate(s=Sum('castka'))['s'] or Decimal('0.00')
    procenta, _ = kam_procento_za_mesic(kam, zacatek, konec)
    return uvolnene + procenta


def kam_naklady_mesic(od_dne, do_dne):
    """Provize uvolněné v daném měsíci (uložené + živé %)."""
    from .models import KeyAccountManager

    ulozene = (
        KamProvize.objects.filter(obdobi=od_dne).aggregate(s=Sum('castka'))['s']
        or Decimal('0.00')
    )
    zive = Decimal('0.00')
    for kam in KeyAccountManager.objects.all():
        pct, _ = kam_procento_za_mesic(kam, od_dne, do_dne)
        zive += pct
    return ulozene + zive


def top_kam_mesic(dnes=None, limit=3):
    from .models import KeyAccountManager

    dnes = dnes or timezone.localdate()
    radky = []
    for kam in KeyAccountManager.objects.filter(aktivni=True):
        dluh = kam_dluh_mesic(kam, dnes)
        if dluh <= 0:
            continue
        radky.append({'kam': kam, 'dluh': dluh})
    radky.sort(key=lambda r: r['dluh'], reverse=True)
    return radky[:limit]


def kam_vypis_data(kam, rok, mesic):
    from calendar import monthrange

    obdobi = date(rok, mesic, 1)
    konec = date(rok, mesic, monthrange(rok, mesic)[1])
    radky = list(
        KamProvize.objects.filter(kam=kam, obdobi=obdobi).select_related('salon').order_by('id')
    )
    procenta_castka, procenta_radky = kam_procento_za_mesic(kam, obdobi, konec)
    k_vyplate = sum(
        (r.castka for r in radky if r.stav == KamProvize.STAV_K_VYPLATE),
        Decimal('0.00'),
    ) + procenta_castka
    return {
        'kam': kam,
        'rok': rok,
        'mesic': mesic,
        'obdobi': obdobi,
        'radky': radky,
        'procenta_radky': procenta_radky,
        'procenta_castka': procenta_castka,
        'k_vyplate': k_vyplate,
        'soucet': sum((r.castka for r in radky), Decimal('0.00')) + procenta_castka,
    }


def oznac_kam_mesic_vyplaceny(kam, rok, mesic, dnes=None):
    dnes = dnes or timezone.localdate()
    data = kam_vypis_data(kam, rok, mesic)
    KamProvize.objects.filter(
        kam=kam,
        obdobi=data['obdobi'],
        stav=KamProvize.STAV_K_VYPLATE,
    ).update(stav=KamProvize.STAV_VYPLACENO, vyplaceno_dne=dnes)
    for radek in data['procenta_radky']:
        KamProvize.objects.get_or_create(
            kam=kam,
            salon=radek['salon'],
            typ=KamProvize.TYP_PROCENTO,
            obdobi=data['obdobi'],
            defaults={
                'castka': radek['castka'],
                'uvolneno_dne': dnes,
                'vyplaceno_dne': dnes,
                'stav': KamProvize.STAV_VYPLACENO,
                'poznamka': f'Procento z přijatého {mesic:02d}/{rok}',
            },
        )
    return data['k_vyplate']


