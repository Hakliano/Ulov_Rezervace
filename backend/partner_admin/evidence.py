"""Evidence vydaných faktur a souhrn za období."""

from datetime import date
from decimal import Decimal

from django.db.models import Sum
from django.urls import reverse
from django.utils import timezone

from .models import ExtraFaktura, KamProvize, PlatbaPartnera, Vydaj


def _castka_cs(hodnota):
    return f'{(hodnota or Decimal("0.00")):.2f}'.replace('.', ',')


def vychozi_obdobi(dnes=None):
    dnes = dnes or timezone.localdate()
    return date(dnes.year, 1, 1), dnes


def parse_datum(raw, fallback):
    text = (raw or '').strip()
    if not text:
        return fallback
    try:
        y, m, d = text.split('-')
        return date(int(y), int(m), int(d))
    except (TypeError, ValueError):
        return fallback


def _castka_platby(platba):
    if platba.prijata_castka is not None:
        return platba.prijata_castka
    return platba.ocekavana_castka


def seznam_faktur(*, od_dne, do_dne, podle='vystaveni'):
    """Sjednotí partnerství i extra faktury. `podle` = vystaveni | uhrada."""
    radky = []
    for platba in PlatbaPartnera.objects.select_related('salon').filter(
        faktura_pdf__isnull=False,
    ).exclude(faktura_pdf=''):
        vystaveni = timezone.localtime(platba.vytvoreno).date() if platba.vytvoreno else platba.zaplaceno_dne
        uhrada = platba.zaplaceno_dne
        klic = vystaveni if podle != 'uhrada' else uhrada
        if klic is None or klic < od_dne or klic > do_dne:
            continue
        radky.append({
            'zdroj': 'partnerstvi',
            'id': platba.id,
            'cislo': platba.cislo_faktury or 'bez čísla',
            'partner': platba.salon.name,
            'salon_id': platba.salon_id,
            'popis': 'Partnerství',
            'castka': _castka_platby(platba),
            'datum_vystaveni': vystaveni,
            'datum_uhrady': uhrada,
            'datum_splatnosti': platba.splatnost,
            'stav': 'Uhrazeno',
            'vs': platba.variabilni_symbol or '',
            'ma_pdf': True,
            'stahnout_url': reverse(
                'partner_admin:stahnout_fakturu_evidence',
                args=['partnerstvi', platba.id],
            ),
            'detail_url': reverse('partner_admin:detail', args=[platba.salon_id]) + '?tab=parovani',
        })

    for faktura in ExtraFaktura.objects.select_related('salon'):
        klic = faktura.datum_vystaveni if podle != 'uhrada' else faktura.datum_uhrady
        if podle == 'uhrada' and klic is None:
            continue
        if klic is None or klic < od_dne or klic > do_dne:
            continue
        radky.append({
            'zdroj': 'extra',
            'id': faktura.id,
            'cislo': faktura.cislo_faktury,
            'partner': faktura.salon.name,
            'salon_id': faktura.salon_id,
            'popis': faktura.popis,
            'castka': faktura.castka,
            'datum_vystaveni': faktura.datum_vystaveni,
            'datum_uhrady': faktura.datum_uhrady,
            'datum_splatnosti': faktura.datum_splatnosti,
            'stav': faktura.get_stav_display(),
            'vs': faktura.variabilni_symbol or '',
            'ma_pdf': bool(faktura.faktura_pdf),
            'stahnout_url': reverse(
                'partner_admin:stahnout_fakturu_evidence',
                args=['extra', faktura.id],
            ),
            'detail_url': reverse('partner_admin:detail', args=[faktura.salon_id]) + '?tab=extra',
        })

    radky.sort(key=lambda r: (r['datum_vystaveni'] or date.min, r['id']), reverse=True)
    return radky


def _datum_label(hodnota):
    if not hodnota:
        return '—'
    return f'{hodnota.day}. {hodnota.month}. {hodnota.year}'


def data_souhrnu(*, od_dne, do_dne, podle='vystaveni'):
    radky = seznam_faktur(od_dne=od_dne, do_dne=do_dne, podle=podle)
    trzby = Decimal('0.00')
    k_uhrade = Decimal('0.00')
    for radek in radky:
        if radek['stav'] == 'K úhradě':
            k_uhrade += radek['castka'] or Decimal('0.00')
        else:
            trzby += radek['castka'] or Decimal('0.00')
    vydaje = (
        Vydaj.objects.filter(datum__gte=od_dne, datum__lte=do_dne).aggregate(s=Sum('castka'))['s']
        or Decimal('0.00')
    )
    kam_map = {}
    for row in KamProvize.objects.filter(
        uvolneno_dne__gte=od_dne,
        uvolneno_dne__lte=do_dne,
    ).select_related('kam'):
        jmeno = row.kam.jmeno
        kam_map[jmeno] = kam_map.get(jmeno, Decimal('0.00')) + row.castka
    kam = [{'jmeno': jmeno, 'castka': _castka_cs(castka)} for jmeno, castka in sorted(kam_map.items())]
    od_label = f'{od_dne.day}. {od_dne.month}. {od_dne.year}'
    do_label = f'{do_dne.day}. {do_dne.month}. {do_dne.year}'
    podle_label = 'data vystavení' if podle != 'uhrada' else 'data úhrady'
    vypis = [
        {
            'cislo': radek['cislo'] or '—',
            'partner': radek['partner'] or '—',
            'polozka': radek['popis'] or '—',
            'vystaveno': _datum_label(radek.get('datum_vystaveni')),
            'uhrada': _datum_label(radek.get('datum_uhrady')),
            'stav': radek['stav'] or '—',
            'castka': f'{_castka_cs(radek.get("castka"))} Kč',
            'vs': radek.get('vs') or '—',
        }
        for radek in radky
    ]
    return {
        'nadpis': f'Souhrn {od_label} – {do_label}',
        'odstavec': (
            f'Přehled faktur vystavených partnerům ULOV KLIENTY podle {podle_label}, '
            f'nákladů na KAM a interních výdajů za zvolené období. Podklad pro hlášení, ne daňový doklad.'
        ),
        'pocet_faktur': len(radky),
        'trzby': _castka_cs(trzby),
        'k_uhrade': _castka_cs(k_uhrade),
        'vydaje': _castka_cs(vydaje),
        'kam': kam,
        'vypis': vypis,
        'obdobi_label': f'Období {od_label} – {do_label} · filtr podle {podle_label}',
        'trzby_raw': trzby,
        'k_uhrade_raw': k_uhrade,
        'vydaje_raw': vydaje,
    }


def vydaje_za_mesic(dnes=None):
    dnes = dnes or timezone.localdate()
    zacatek = dnes.replace(day=1)
    hodnota = Vydaj.objects.filter(datum__gte=zacatek, datum__lte=dnes).aggregate(s=Sum('castka'))['s']
    return hodnota or Decimal('0.00')
