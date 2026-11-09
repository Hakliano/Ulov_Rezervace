from datetime import datetime as dt_cls, time as dt_time, timedelta

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_http_methods, require_POST

from .kalendar_models import KalendarUdalost
from .kalendar_services import (
    aktivni_uzivatele,
    klient_volby,
    mesic_bunky,
    mesic_sousedni,
    muze_editovat,
    datum_z_pozadavku,
    parse_cas,
    parse_den,
    try_parse_den,
    queryset_pro_uzivatele,
    rozparsovat_klient,
    tyden_rozsah,
)
from .klienti_constants import PROJEKT_HYA, PROJEKT_MODERNIK
from .klienti_models import KlientHya, KlientModernik
from .views import login_required_view


def _local_dt(value):
    if not value:
        return None
    raw = str(value).strip()
    dt = parse_datetime(raw)
    if dt is None:
        try:
            dt = dt_cls.fromisoformat(raw)
        except ValueError:
            return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def _klient_vyber(udalost):
    if udalost and udalost.klient_modernik_id:
        return f'{PROJEKT_MODERNIK}:{udalost.klient_modernik_id}'
    if udalost and udalost.klient_hya_id:
        return f'{PROJEKT_HYA}:{udalost.klient_hya_id}'
    return ''


def _form_context(udalost=None):
    return {
        'typy': KalendarUdalost.TYPY,
        'uzivatele': aktivni_uzivatele(),
        'klienti_volby': klient_volby(),
        'klient_vyber': _klient_vyber(udalost),
        'udalost': udalost,
    }


def _bind_klient(udalost, klic):
    projekt, pk = rozparsovat_klient(klic)
    udalost.klient_modernik = None
    udalost.klient_hya = None
    if projekt == PROJEKT_MODERNIK and pk:
        udalost.klient_modernik = get_object_or_404(KlientModernik, pk=pk)
    elif projekt == PROJEKT_HYA and pk:
        udalost.klient_hya = get_object_or_404(KlientHya, pk=pk)


def _validate_interval(zacatek, konec):
    if not zacatek or not konec:
        return 'Vyplňte začátek i konec.'
    if konec < zacatek:
        return 'Konec musí být po začátku.'
    return ''


def _fill_from_post(udalost, post, user):
    udalost.nazev = (post.get('nazev') or '').strip()[:200]
    udalost.typ = post.get('typ') or KalendarUdalost.TYP_OSTATNI
    if udalost.typ not in dict(KalendarUdalost.TYPY):
        udalost.typ = KalendarUdalost.TYP_OSTATNI
    udalost.popis = (post.get('popis') or '').strip()
    uid = post.get('prirazeny') or user.pk
    udalost.prirazeny_id = int(uid) if str(uid).isdigit() else user.pk
    udalost.zacatek = _local_dt(post.get('zacatek'))
    udalost.konec = _local_dt(post.get('konec'))
    udalost.hotovo = post.get('hotovo') == 'on' if udalost.typ == KalendarUdalost.TYP_UKOL else False
    _bind_klient(udalost, post.get('klient') or '')


@login_required_view
def kalendar(request):
    zobrazeni = (request.GET.get('z') or 'mesic').strip()
    if zobrazeni not in ('mesic', 'tyden', 'seznam'):
        zobrazeni = 'mesic'
    filtr = (request.GET.get('u') or '').strip()
    anchor = datum_z_pozadavku(request) or parse_den(request.GET.get('den'))
    dnes = timezone.localdate()
    qs = queryset_pro_uzivatele(request.user, filtr_uzivatel=filtr)
    if zobrazeni == 'mesic':
        start_d = anchor.replace(day=1)
        if start_d.month == 12:
            end_d = start_d.replace(year=start_d.year + 1, month=1)
        else:
            end_d = start_d.replace(month=start_d.month + 1)
        start_dt = timezone.make_aware(dt_cls.combine(start_d, dt_time.min))
        end_dt = timezone.make_aware(dt_cls.combine(end_d, dt_time.min))
        udalosti = list(qs.filter(zacatek__lt=end_dt, konec__gte=start_dt))
        cells, by_day = mesic_bunky(anchor.year, anchor.month, udalosti)
        pred_mesic, dalsi_mesic = mesic_sousedni(anchor)
        ctx = {
            'cells': cells,
            'by_day': by_day,
            'anchor': anchor,
            'pred_mesic': pred_mesic,
            'dalsi_mesic': dalsi_mesic,
        }
    elif zobrazeni == 'tyden':
        days = tyden_rozsah(anchor)
        start = timezone.make_aware(dt_cls.combine(days[0], dt_time.min))
        end = start + timedelta(days=7)
        udalosti = list(qs.filter(zacatek__lt=end, konec__gte=start))
        by_day = {d: [] for d in days}
        for u in udalosti:
            by_day[timezone.localtime(u.zacatek).date()].append(u)
        ctx = {'days': days, 'by_day': by_day, 'anchor': anchor}
    else:
        now = timezone.now()
        udalosti = list(qs.filter(konec__gte=now).order_by('zacatek')[:100])
        jen_ukoly = request.GET.get('ukoly') == '1'
        if jen_ukoly:
            udalosti = [u for u in udalosti if u.typ == KalendarUdalost.TYP_UKOL and not u.hotovo]
        ctx = {'udalosti': udalosti, 'jen_ukoly': jen_ukoly, 'anchor': anchor}
    return render(request, 'kalendar.html', {
        'zobrazeni': zobrazeni,
        'filtr': filtr,
        'uzivatele': aktivni_uzivatele(),
        'typy': KalendarUdalost.TYPY,
        'dnes': dnes,
        **ctx,
    })


@login_required_view
@require_http_methods(['GET', 'POST'])
def kalendar_nova(request):
    raw_den = (request.GET.get('datum') or request.GET.get('den') or '').strip()
    udalost = KalendarUdalost(prirazeny=request.user, vytvoril=request.user)
    if raw_den and not request.POST:
        d = try_parse_den(raw_den)
        if d is None:
            messages.warning(request, 'Neplatné datum v odkazu — vyberte datum ve formuláři.')
        else:
            cas = parse_cas(request.GET.get('cas'))
            start = timezone.make_aware(dt_cls.combine(d, cas or dt_time(9, 0)))
            end = start + timedelta(hours=1)
            udalost.zacatek = start
            udalost.konec = end
    if request.method == 'POST':
        udalost.vytvoril = request.user
        _fill_from_post(udalost, request.POST, request.user)
        chyba = _validate_interval(udalost.zacatek, udalost.konec)
        if not udalost.nazev:
            chyba = 'Zadejte název.'
        if chyba:
            messages.error(request, chyba)
        else:
            udalost.save()
            messages.success(request, 'Událost je uložená.')
            return redirect('kalendar_detail', pk=udalost.pk)
    return render(request, 'kalendar_form.html', {
        'nova': True,
        'form_action': 'nova',
        **_form_context(udalost),
    })


@login_required_view
def kalendar_detail(request, pk):
    udalost = get_object_or_404(
        KalendarUdalost.objects.select_related('prirazeny', 'klient_modernik', 'klient_hya'),
        pk=pk,
    )
    return render(request, 'kalendar_detail.html', {
        'udalost': udalost,
        'muze_editovat': muze_editovat(request.user, udalost),
    })


@login_required_view
@require_http_methods(['GET', 'POST'])
def kalendar_upravit(request, pk):
    udalost = get_object_or_404(KalendarUdalost, pk=pk)
    if not muze_editovat(request.user, udalost):
        raise PermissionDenied
    if request.method == 'POST':
        _fill_from_post(udalost, request.POST, request.user)
        chyba = _validate_interval(udalost.zacatek, udalost.konec)
        if not udalost.nazev:
            chyba = 'Zadejte název.'
        if chyba:
            messages.error(request, chyba)
        else:
            udalost.save()
            messages.success(request, 'Událost je uložená.')
            return redirect('kalendar_detail', pk=pk)
    return render(request, 'kalendar_form.html', {
        'nova': False,
        'form_action': 'upravit',
        **_form_context(udalost),
    })


@login_required_view
@require_POST
def kalendar_smazat(request, pk):
    udalost = get_object_or_404(KalendarUdalost, pk=pk)
    if not muze_editovat(request.user, udalost):
        raise PermissionDenied
    udalost.delete()
    messages.success(request, 'Událost je smazaná.')
    return redirect('kalendar')


@login_required_view
@require_POST
def kalendar_hotovo(request, pk):
    udalost = get_object_or_404(KalendarUdalost, pk=pk)
    if not muze_editovat(request.user, udalost):
        raise PermissionDenied
    if udalost.typ != KalendarUdalost.TYP_UKOL:
        messages.error(request, 'Jen úkol lze označit jako hotový.')
        return redirect('kalendar_detail', pk=pk)
    udalost.hotovo = request.POST.get('hotovo', '1') == '1'
    udalost.save(update_fields=['hotovo', 'upraveno'])
    back = request.POST.get('next') or reverse('kalendar')
    return redirect(back)
