from calendar import monthrange
from datetime import date
from decimal import Decimal

from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import HromadnyEmail, PartnerNastaveni, PlatbaPartnera, TechnickaChyba


def _castka_plateb(od_dne, do_dne):
    hodnota = PlatbaPartnera.objects.filter(
        zaplaceno_dne__gte=od_dne,
        zaplaceno_dne__lte=do_dne,
    ).aggregate(celkem=Sum(Coalesce('prijata_castka', 'ocekavana_castka')))['celkem']
    return hodnota or Decimal('0.00')


def _zacatek_mesice(den):
    return den.replace(day=1)


def _konec_mesice(den):
    return den.replace(day=monthrange(den.year, den.month)[1])


def _predchozi_mesic(den):
    if den.month == 1:
        return den.replace(year=den.year - 1, month=12, day=1)
    return den.replace(month=den.month - 1, day=1)


def _mesice_zpet(dnes, pocet=12):
    rok, mesic = dnes.year, dnes.month
    radky = []
    for _ in range(pocet):
        radky.append((rok, mesic))
        mesic -= 1
        if mesic == 0:
            mesic = 12
            rok -= 1
    radky.reverse()
    return radky


def email_partnera(partner):
    return (partner.fakturacni_email or getattr(partner.salon, 'email', '') or '').strip()


def prijemci_hromadneho_emailu(okruh, tarif=''):
    dnes = timezone.localdate()
    qs = PartnerNastaveni.objects.select_related('salon')
    if okruh == HromadnyEmail.OKRUH_PO_SPLATNOSTI:
        qs = qs.filter(dalsi_splatnost__lt=dnes)
    elif okruh == HromadnyEmail.OKRUH_ACTIVE:
        qs = qs.filter(stav=PartnerNastaveni.STAV_ACTIVE)
    elif okruh == HromadnyEmail.OKRUH_TARIF:
        qs = qs.filter(tarif=(tarif or '').strip())
    videne = set()
    prijemci = []
    preskoceno = 0
    for partner in qs:
        adresa = email_partnera(partner).lower()
        if not adresa:
            preskoceno += 1
            continue
        if adresa in videne:
            continue
        videne.add(adresa)
        prijemci.append((partner, adresa))
    return prijemci, preskoceno


def data_prehledu(dnes=None):
    dnes = dnes or timezone.localdate()
    _zacatek = _zacatek_mesice(dnes)
    minuly = _predchozi_mesic(dnes)
    partneri = list(PartnerNastaveni.objects.select_related('salon'))
    po_splatnosti = [p for p in partneri if p.je_po_splatnosti]
    po_splatnosti.sort(key=lambda p: p.dalsi_splatnost or dnes)
    bez_vs = sum(1 for p in partneri if not p.variabilni_symbol)
    blokovanych = sum(1 for p in partneri if p.stav == PartnerNastaveni.STAV_BLOCKED)
    mesicni_tarif = Decimal('0.00')
    for p in partneri:
        if p.stav != PartnerNastaveni.STAV_ACTIVE:
            continue
        if p.periodicita == PartnerNastaveni.PERIODA_ROK:
            mesicni_tarif += (p.castka or Decimal('0.00')) / Decimal('12')
        else:
            mesicni_tarif += p.castka or Decimal('0.00')

    tarify = []
    skupiny = {}
    for p in partneri:
        nazev = (p.tarif or '').strip() or 'Bez tarifu'
        skupiny[nazev] = skupiny.get(nazev, 0) + 1
    max_tarif = max(skupiny.values()) if skupiny else 1
    for nazev, pocet in sorted(skupiny.items(), key=lambda item: (-item[1], item[0])):
        tarify.append({
            'nazev': nazev,
            'pocet': pocet,
            'pct': round(pocet / max_tarif * 100),
        })

    mesice = _mesice_zpet(dnes, 12)
    nove = {(rok, mesic): 0 for rok, mesic in mesice}
    prvni = date(mesice[0][0], mesice[0][1], 1)
    kumulativne = PartnerNastaveni.objects.filter(zalozeno__date__lt=prvni).count()
    for dt in PartnerNastaveni.objects.values_list('zalozeno', flat=True):
        if not dt:
            continue
        lokalni = timezone.localtime(dt).date()
        klic = (lokalni.year, lokalni.month)
        if klic in nove:
            nove[klic] += 1
    rust = []
    maxima = 1
    for rok, mesic in mesice:
        kumulativne += nove[(rok, mesic)]
        maxima = max(maxima, kumulativne)
        rust.append({
            'label': f'{mesic:02d}',
            'rok': rok,
            'nove': nove[(rok, mesic)],
            'celkem': kumulativne,
        })
    for radek in rust:
        radek['pct'] = round(radek['celkem'] / maxima * 100) if maxima else 0

    upozorneni = []
    if po_splatnosti:
        upozorneni.append({
            'typ': 'crit',
            'text': f'{len(po_splatnosti)} partnerů je po splatnosti.',
            'odkaz': 'partneri-po-splatnosti',
        })
    if blokovanych:
        upozorneni.append({
            'typ': 'warn',
            'text': f'{blokovanych} partnerů je BLOCKED.',
            'odkaz': 'partneri',
        })
    if bez_vs:
        upozorneni.append({
            'typ': 'warn',
            'text': f'{bez_vs} partnerů nemá variabilní symbol.',
            'odkaz': 'partneri-bez-vs',
        })
    nevyresene = TechnickaChyba.objects.filter(vyreseno=False).select_related('salon')
    pocet_chyb = nevyresene.count()
    if pocet_chyb:
        upozorneni.append({
            'typ': 'crit',
            'text': f'{pocet_chyb} nevyřešených technických chyb.',
            'odkaz': 'chyby',
        })

    return {
        'prijato_mesic': _castka_plateb(_zacatek, dnes),
        'prijato_minuly': _castka_plateb(_zacatek_mesice(minuly), _konec_mesice(minuly)),
        'mesicni_tarif': mesicni_tarif.quantize(Decimal('0.01')),
        'partneru': len(partneri),
        'po_splatnosti_pocet': len(po_splatnosti),
        'blokovanych': blokovanych,
        'po_splatnosti': po_splatnosti[:6],
        'tarify': tarify,
        'rust': rust,
        'upozorneni': upozorneni[:4],
        'chyby': list(nevyresene[:5]),
    }
