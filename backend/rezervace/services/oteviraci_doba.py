"""Otevírací doba salonu odvozená ze sjednocení pracovních dob aktivních zaměstnanců."""

from salons.models import OteviraciDoba, Salon

from rezervace.models import Zamestnanec, ZamestnanecRozvrh


def _den_nazev(den: int) -> str:
    return dict(OteviraciDoba.DENY)[den]


def rozvrh_dne_pro_zamestnance(zamestnanec: Zamestnanec, den: int):
    try:
        return zamestnanec.rozvrh.get(den=den)
    except ZamestnanecRozvrh.DoesNotExist:
        return None


def vypocti_oteviraci_okno_dne(salon: Salon, den: int):
    """Nejdřívější začátek a nejpozdější konec mezi aktivními zaměstnanci v daný den týdne."""
    od_times = []
    do_times = []
    for z in Zamestnanec.objects.filter(salon=salon, aktivni=True).exclude(
        role=Zamestnanec.ROLE_MAJITEL,
    ).prefetch_related('rozvrh'):
        roz = rozvrh_dne_pro_zamestnance(z, den)
        if roz and not roz.volno and roz.od and roz.do:
            od_times.append(roz.od)
            do_times.append(roz.do)
    if not od_times:
        return None
    return min(od_times), max(do_times)


def vypocti_oteviraci_dobu_tydne(salon: Salon) -> list[dict]:
    """Sedm dní — pro každý den min(od) a max(do), nebo zavřeno když nikdo nepracuje."""
    staff = list(
        Zamestnanec.objects.filter(salon=salon, aktivni=True).exclude(
            role=Zamestnanec.ROLE_MAJITEL,
        ).prefetch_related('rozvrh'),
    )
    result = []
    for den in range(7):
        od_times = []
        do_times = []
        for z in staff:
            roz = rozvrh_dne_pro_zamestnance(z, den)
            if roz and not roz.volno and roz.od and roz.do:
                od_times.append(roz.od)
                do_times.append(roz.do)
        if od_times:
            result.append({
                'den': den,
                'den_nazev': _den_nazev(den),
                'od': min(od_times),
                'do': max(do_times),
                'zavreno': False,
            })
        else:
            result.append({
                'den': den,
                'den_nazev': _den_nazev(den),
                'od': None,
                'do': None,
                'zavreno': True,
            })
    return result
