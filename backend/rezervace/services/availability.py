from datetime import datetime, timedelta
from typing import Iterable

from django.db.models import Max, Q
from django.utils import timezone

from rezervace.models import (
    BlokaceCasu,
    Rezervace,
    SalonVyjimka,
    StatniSvatky,
    Zamestnanec,
    ZamestnanecAbsence,
    ZamestnanecRozvrh,
    ZamestnanecSluzba,
)
from rezervace.services.oteviraci_doba import vypocti_oteviraci_okno_dne
from salons.models import CenikPolozka, Salon


AKTIVNI_STAVY = ('ceka', 'potvrzeno')
VYTEZ_STAVY = ('ceka', 'potvrzeno', 'dokonceno')
_NIKDY = datetime(1970, 1, 1)


def _combine(d, t):
    return timezone.make_aware(datetime.combine(d, t))


def salon_je_zavreny(salon: Salon, datum) -> bool:
    if StatniSvatky.objects.filter(datum=datum).exists():
        return True
    if SalonVyjimka.objects.filter(
        salon=salon, datum_od__lte=datum, datum_do__gte=datum,
    ).exists():
        return True
    return vypocti_oteviraci_okno_dne(salon, datum.weekday()) is None


def salon_oteviraci_okno(salon: Salon, datum):
    if salon_je_zavreny(salon, datum):
        return None
    return vypocti_oteviraci_okno_dne(salon, datum.weekday())


def zamestnanec_dostupny(zamestnanec: Zamestnanec, datum) -> bool:
    if zamestnanec.role == Zamestnanec.ROLE_MAJITEL:
        return False
    if not zamestnanec.aktivni:
        return False
    if ZamestnanecAbsence.objects.filter(
        zamestnanec=zamestnanec,
        stav=ZamestnanecAbsence.STAV_SCHVALENO,
        datum_od__lte=datum,
        datum_do__gte=datum,
    ).exists():
        return False
    den = datum.weekday()
    try:
        roz = zamestnanec.rozvrh.get(den=den)
    except ZamestnanecRozvrh.DoesNotExist:
        return False
    return not roz.volno and roz.od and roz.do


def zamestnanec_okno(zamestnanec: Zamestnanec, datum):
    if not zamestnanec_dostupny(zamestnanec, datum):
        return None
    roz = zamestnanec.rozvrh.get(den=datum.weekday())
    return roz.od, roz.do


def celkova_delka_sluzby(sluzby: Iterable[CenikPolozka]) -> int:
    total = 0
    for s in sluzby:
        total += s.delka_minut + s.rezerva_minut
    return total or 30


def _prekryva(start, end, obs_start, obs_end) -> bool:
    return start < obs_end and end > obs_start


def _obsazenost_zamestnance(zamestnanec, salon, start, end, exclude_id=None):
    qs = Rezervace.objects.filter(
        salon=salon,
        stav__in=AKTIVNI_STAVY,
        zacatek__lt=end,
        konec__gt=start,
        zamestnanec=zamestnanec,
    )
    if exclude_id:
        qs = qs.exclude(pk=exclude_id)
    return qs.exists()


def _blokace_koliduje(salon, zamestnanec, start, end):
    qs = BlokaceCasu.objects.filter(
        salon=salon, zacatek__lt=end, konec__gt=start,
    )
    if zamestnanec:
        qs = qs.filter(Q(zamestnanec=zamestnanec) | Q(zamestnanec__isnull=True))
    return qs.exists()


def zamestnanec_umi_sluzby(zamestnanec: Zamestnanec, sluzby_ids: Iterable[int] | None) -> bool:
    """Prázdné přiřazení = umí vše. Jinak musí umět všechny požadované služby."""
    if not sluzby_ids:
        return True
    ids = {int(x) for x in sluzby_ids}
    assigned = set(
        ZamestnanecSluzba.objects.filter(zamestnanec=zamestnanec).values_list('sluzba_id', flat=True),
    )
    if not assigned:
        return True
    return ids.issubset(assigned)


def volni_zamestnanci(salon: Salon, datum, start, end, exclude_id=None, sluzby_ids=None):
    staff = Zamestnanec.objects.filter(salon=salon, aktivni=True).exclude(role=Zamestnanec.ROLE_MAJITEL)
    # Rozvrh je v lokálním čase salonu — nebrat UTC wall-clock z DB.
    start_local = timezone.localtime(start) if timezone.is_aware(start) else start
    end_local = timezone.localtime(end) if timezone.is_aware(end) else end
    volni = []
    for z in staff:
        if not zamestnanec_umi_sluzby(z, sluzby_ids):
            continue
        okno = zamestnanec_okno(z, datum)
        if not okno:
            continue
        od, do = okno
        if start_local.time() < od or end_local.time() > do:
            continue
        if _obsazenost_zamestnance(z, salon, start, end, exclude_id):
            continue
        if _blokace_koliduje(salon, z, start, end):
            continue
        volni.append(z)
    return volni


def generuj_terminy(
    salon: Salon,
    datum,
    sluzby_ids: list[int],
    zamestnanec_id=None,
    exclude_rezervace_id=None,
):
    from rezervace.models import RezervacniNastaveni

    try:
        nastaveni = salon.rezervacni_nastaveni
    except RezervacniNastaveni.DoesNotExist:
        return []

    sluzby = list(
        CenikPolozka.objects.filter(
            salon=salon, pk__in=sluzby_ids, aktivni=True,
        ).order_by('poradi'),
    )
    if not sluzby or len(sluzby) != len(sluzby_ids):
        return []

    delka = celkova_delka_sluzby(sluzby)
    interval = nastaveni.interval_minut

    okno = salon_oteviraci_okno(salon, datum)
    if not okno:
        return []

    salon_od, salon_do = okno
    now = timezone.now()
    min_start = now + timedelta(hours=nastaveni.min_predstih_hodin)
    max_date = (now + timedelta(days=nastaveni.max_predstih_mesicu * 30)).date()
    if datum > max_date:
        return []

    terminy = []
    current = datetime.combine(datum, salon_od)
    end_limit = datetime.combine(datum, salon_do)

    while current + timedelta(minutes=delka) <= end_limit:
        start = timezone.make_aware(current)
        end = start + timedelta(minutes=delka)

        if start >= min_start:
            if zamestnanec_id:
                try:
                    z = Zamestnanec.objects.get(
                        pk=zamestnanec_id, salon=salon, aktivni=True,
                    )
                except Zamestnanec.DoesNotExist:
                    return []
                if z.role == Zamestnanec.ROLE_MAJITEL:
                    return []
                if not zamestnanec_umi_sluzby(z, sluzby_ids):
                    return []
                okno_z = zamestnanec_okno(z, datum)
                if okno_z:
                    z_od, z_do = okno_z
                    start_local = timezone.localtime(start) if timezone.is_aware(start) else start
                    end_local = timezone.localtime(end) if timezone.is_aware(end) else end
                    if start_local.time() >= z_od and end_local.time() <= z_do:
                        if not _obsazenost_zamestnance(z, salon, start, end, exclude_rezervace_id):
                            if not _blokace_koliduje(salon, z, start, end):
                                terminy.append({
                                    'cas': start_local.strftime('%H:%M'),
                                    'zamestnanec_id': z.id,
                                    'zamestnanec': z.jmeno,
                                })
            else:
                volni = volni_zamestnanci(
                    salon, datum, start, end, exclude_rezervace_id, sluzby_ids=sluzby_ids,
                )
                if volni:
                    terminy.append({
                        'cas': start.strftime('%H:%M'),
                        'zamestnanec_id': None,
                        'zamestnanec': 'Kdokoliv',
                        'dostupni': [{'id': z.id, 'jmeno': z.jmeno} for z in volni],
                    })

        current += timedelta(minutes=interval)

    return terminy


def _smena_minuty(zamestnanec, datum):
    okno = zamestnanec_okno(zamestnanec, datum)
    if not okno:
        return 0
    od, do = okno
    return max((datetime.combine(datum, do) - datetime.combine(datum, od)).total_seconds() / 60, 0)


def _obsazene_minuty_den(staff_ids, salon, datum):
    if not staff_ids:
        return {}
    den_od = timezone.make_aware(datetime.combine(datum, datetime.min.time()))
    den_do = den_od + timedelta(days=1)
    minuty = {sid: 0.0 for sid in staff_ids}
    radky = Rezervace.objects.filter(
        salon=salon,
        zamestnanec_id__in=staff_ids,
        stav__in=VYTEZ_STAVY,
        zacatek__lt=den_do,
        konec__gt=den_od,
    ).values_list('zamestnanec_id', 'zacatek', 'konec')
    for zid, zacatek, konec in radky:
        start = max(zacatek, den_od)
        end = min(konec, den_do)
        if end > start:
            minuty[zid] += (end - start).total_seconds() / 60
    return minuty


def _posledni_rezervace_map(staff_ids):
    if not staff_ids:
        return {}
    radky = (
        Rezervace.objects.filter(
            zamestnanec_id__in=staff_ids,
            stav__in=VYTEZ_STAVY,
        )
        .values('zamestnanec_id')
        .annotate(posledni=Max('zacatek'))
    )
    return {r['zamestnanec_id']: r['posledni'] for r in radky}


def _vyber_spravedlive(volni, salon, datum):
    """Nejnižší % vytížení ten den, při shodě kdo čeká nejdéle, pak pořadí."""
    if not volni:
        return None
    if len(volni) == 1:
        return volni[0]
    ids = [z.id for z in volni]
    obsazeno = _obsazene_minuty_den(ids, salon, datum)
    posledni = _posledni_rezervace_map(ids)
    smeny = {z.id: _smena_minuty(z, datum) for z in volni}

    def klic(z):
        smena = smeny.get(z.id) or 0
        vytez = (obsazeno.get(z.id, 0) / smena) if smena else 1.0
        cekal_od = posledni.get(z.id) or _NIKDY
        if timezone.is_aware(cekal_od):
            cekal_od = timezone.make_naive(cekal_od)
        return (vytez, cekal_od, z.poradi, z.id)

    return min(volni, key=klic)


def prirad_zamestnance(salon, datum, start, end, preferovany_id=None, sluzby_ids=None):
    volni = volni_zamestnanci(salon, datum, start, end, sluzby_ids=sluzby_ids)
    if preferovany_id:
        for z in volni:
            if z.id == preferovany_id:
                return z
        return None
    return _vyber_spravedlive(volni, salon, datum)
