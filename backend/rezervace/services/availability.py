from datetime import datetime, timedelta
from typing import Iterable

from django.db.models import Q
from django.utils import timezone

from rezervace.models import (
    BlokaceCasu,
    Rezervace,
    SalonVyjimka,
    StatniSvatky,
    Zamestnanec,
    ZamestnanecAbsence,
    ZamestnanecRozvrh,
)
from rezervace.services.oteviraci_doba import vypocti_oteviraci_okno_dne
from salons.models import CenikPolozka, Salon


AKTIVNI_STAVY = ('ceka', 'potvrzeno')


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
        zamestnanec=zamestnanec, datum_od__lte=datum, datum_do__gte=datum,
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


def volni_zamestnanci(salon: Salon, datum, start, end, exclude_id=None):
    staff = Zamestnanec.objects.filter(salon=salon, aktivni=True).exclude(role=Zamestnanec.ROLE_MAJITEL)
    # Rozvrh je v lokálním čase salonu — nebrat UTC wall-clock z DB.
    start_local = timezone.localtime(start) if timezone.is_aware(start) else start
    end_local = timezone.localtime(end) if timezone.is_aware(end) else end
    volni = []
    for z in staff:
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
                volni = volni_zamestnanci(salon, datum, start, end, exclude_rezervace_id)
                if volni:
                    terminy.append({
                        'cas': start.strftime('%H:%M'),
                        'zamestnanec_id': None,
                        'zamestnanec': 'Kdokoliv',
                        'dostupni': [{'id': z.id, 'jmeno': z.jmeno} for z in volni],
                    })

        current += timedelta(minutes=interval)

    return terminy


def prirad_zamestnance(salon, datum, start, end, preferovany_id=None):
    if preferovany_id:
        volni = volni_zamestnanci(salon, datum, start, end)
        for z in volni:
            if z.id == preferovany_id:
                return z
        return None
    volni = volni_zamestnanci(salon, datum, start, end)
    return volni[0] if volni else None
