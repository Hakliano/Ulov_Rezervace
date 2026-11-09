from __future__ import annotations

from calendar import monthcalendar
from datetime import date, datetime, timedelta, time as dt_time

from django.contrib.auth.models import User
from django.utils import timezone

from .kalendar_models import KalendarUdalost


def muze_editovat(user, udalost: KalendarUdalost) -> bool:
    return user.is_superuser or udalost.prirazeny_id == user.pk


def queryset_pro_uzivatele(user, *, filtr_uzivatel=None):
    qs = KalendarUdalost.objects.select_related(
        'prirazeny', 'klient_modernik', 'klient_hya',
    )
    if filtr_uzivatel == 'me':
        qs = qs.filter(prirazeny=user)
    elif filtr_uzivatel and str(filtr_uzivatel).isdigit():
        qs = qs.filter(prirazeny_id=int(filtr_uzivatel))
    return qs


def try_parse_den(raw):
    if not raw:
        return None
    try:
        return date.fromisoformat(str(raw).strip()[:10])
    except ValueError:
        return None


def parse_den(raw):
    return try_parse_den(raw) or timezone.localdate()


def parse_cas(raw):
    if not raw:
        return None
    text = str(raw).strip()[:5]
    try:
        parts = text.split(':')
        if len(parts) != 2:
            return None
        h, m = int(parts[0]), int(parts[1])
        if 0 <= h <= 23 and 0 <= m <= 59:
            return dt_time(h, m)
    except ValueError:
        return None
    return None


def datum_z_pozadavku(request):
    raw = (request.GET.get('datum') or request.GET.get('den') or '').strip()
    return try_parse_den(raw) if raw else None


def mesic_bunky(rok, mesic, udalosti):
    weeks = monthcalendar(rok, mesic)
    cells = []
    for week in weeks:
        row = []
        for day in week:
            if day == 0:
                row.append(None)
            else:
                row.append(date(rok, mesic, day))
        cells.append(row)
    by_day = {}
    for u in udalosti:
        loc = timezone.localtime(u.zacatek).date()
        by_day.setdefault(loc, []).append(u)
    return cells, by_day


def mesic_sousedni(anchor: date):
    if anchor.month == 1:
        pred = date(anchor.year - 1, 12, 1)
    else:
        pred = date(anchor.year, anchor.month - 1, 1)
    if anchor.month == 12:
        dalsi = date(anchor.year + 1, 1, 1)
    else:
        dalsi = date(anchor.year, anchor.month + 1, 1)
    return pred, dalsi


def tyden_rozsah(anchor: date):
    start = anchor - timedelta(days=anchor.weekday())
    return [start + timedelta(days=i) for i in range(7)]


def dnesni_program(user):
    start = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return list(
        KalendarUdalost.objects.filter(
            prirazeny=user,
            typ__in=[KalendarUdalost.TYP_SCHUZKA, KalendarUdalost.TYP_TELEFONAT],
            zacatek__lt=end,
            konec__gte=start,
        ).select_related('klient_modernik', 'klient_hya').order_by('zacatek')
    )


def moje_ukoly(user, limit=8):
    now = timezone.now()
    qs = (
        KalendarUdalost.objects.filter(
            prirazeny=user,
            typ=KalendarUdalost.TYP_UKOL,
            hotovo=False,
        )
        .select_related('klient_modernik', 'klient_hya')
        .order_by('konec', 'zacatek')
    )
    po_terminu = qs.filter(konec__lt=now).count()
    return list(qs[:limit]), po_terminu


def klient_udalosti_modernik(klient):
    return KalendarUdalost.objects.filter(klient_modernik=klient).select_related('prirazeny')[:20]


def klient_udalosti_hya(klient):
    return KalendarUdalost.objects.filter(klient_hya=klient).select_related('prirazeny')[:20]


def aktivni_uzivatele():
    return User.objects.filter(is_active=True).order_by('first_name', 'username')


def klient_volby():
    from .klienti_constants import PROJEKT_HYA, PROJEKT_MODERNIK
    from .klienti_models import KlientHya, KlientModernik

    volby = [('', '— bez klienta —')]
    for k in KlientModernik.objects.order_by('jmeno')[:500]:
        volby.append((f'{PROJEKT_MODERNIK}:{k.pk}', f'Moderník — {k.jmeno}'))
    for k in KlientHya.objects.order_by('jmeno')[:500]:
        volby.append((f'{PROJEKT_HYA}:{k.pk}', f'HereYouAre — {k.jmeno}'))
    return volby


def rozparsovat_klient(klic):
    if not klic or ':' not in klic:
        return None, None
    projekt, pk = klic.split(':', 1)
    if not pk.isdigit():
        return None, None
    return projekt, int(pk)
