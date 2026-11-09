from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_http_methods, require_POST

from .hya_client import HyaApiError, detail as hya_detail, meta_statuses, upravit as hya_upravit, vytvorit as hya_vytvorit, zmenit_stav as hya_zmenit_stav
from .klienti_constants import PROJEKT_HYA, PROJEKT_MODERNIK, PROJEKTY, SYNC_META_HYA, SYNC_META_MODERNIK
from .klienti_models import KlientHya, KlientModernik, KlientSektor, KlientStavHistorie, KlientSyncMeta
from .klienti_sync import bootstrap_if_empty, maybe_auto_nocni_sync, synchronizuj_klienty, upsert_klient, upsert_klient_hya
from .modernik_client import ModernikApiError, detail as api_detail, meta as api_meta, upravit as api_upravit, vytvorit as api_vytvorit, zmenit_stav as api_zmenit_stav
from .kalendar_services import klient_udalosti_hya, klient_udalosti_modernik
from .views import login_required_view


def _crm_zapis_povolen(projekt: str) -> bool:
    if projekt == PROJEKT_HYA:
        return bool(getattr(settings, 'POSTAK_HYA_CRM_WRITE', False))
    if projekt == PROJEKT_MODERNIK:
        return bool(getattr(settings, 'POSTAK_MODERNIK_CRM_WRITE', False))
    return False


def _odmitnout_zapis(request, projekt: str):
    messages.error(
        request,
        'Zápis do CRM je na tomto prostředí vypnutý (pouze čtení a synchronizace).',
    )
    return redirect('klienti')


PER_PAGE = (25, 50, 100)
PROJEKT_MAP = dict(PROJEKTY)


def _kdo(request):
    return (request.user.get_full_name() or request.user.get_username() or '')[:120]


def _lokal(projekt, pk):
    if projekt == PROJEKT_HYA:
        return get_object_or_404(KlientHya, pk=pk)
    return get_object_or_404(KlientModernik, pk=pk)


def _sync_historie(klient, rows):
    KlientStavHistorie.objects.filter(klient=klient).delete()
    for h in rows or []:
        kdy = parse_datetime(h.get('kdy') or '') or klient.remote_upraveno
        KlientStavHistorie.objects.create(
            klient=klient,
            stav=h.get('stav', ''),
            stav_pred=h.get('stav_pred', ''),
            stav_label=h.get('stav_label', ''),
            kdo=h.get('kdo', ''),
            kdy=kdy,
        )


def _apply_modernik(request, data, ok_msg):
    k = data.get('kontakt')
    if not k:
        raise ModernikApiError('Moderník nevrátil záznam.')
    upsert_klient(k)
    messages.success(request, ok_msg)
    return get_object_or_404(KlientModernik, remote_id=k['id'])


def _apply_hya(request, data, ok_msg):
    k = data.get('client')
    if not k:
        raise HyaApiError('HYA nevrátil záznam.')
    upsert_klient_hya(k)
    messages.success(request, ok_msg)
    return get_object_or_404(KlientHya, remote_id=k['id'])


def _conflict_modernik(request, exc):
    if exc.code == 'conflict' and exc.payload.get('kontakt'):
        upsert_klient(exc.payload['kontakt'])
        messages.error(request, f'{exc} Obnovte stránku.')
        return True
    messages.error(request, str(exc))
    return False


def _conflict_hya(request, exc):
    if exc.status == 409 and exc.payload.get('client'):
        upsert_klient_hya(exc.payload['client'])
        messages.error(request, f'{exc} Obnovte stránku.')
        return True
    messages.error(request, str(exc))
    return False


def _load_stavy(projekt, stavy_mod, stavy_hya):
    if projekt == PROJEKT_MODERNIK:
        return stavy_mod
    if projekt == PROJEKT_HYA:
        return stavy_hya
    out = []
    for s in stavy_mod:
        row = dict(s)
        row['label'] = f"Moderník — {s['label']}"
        row['projekt'] = PROJEKT_MODERNIK
        out.append(row)
    for s in stavy_hya:
        row = dict(s)
        row['label'] = f"HereYouAre — {s['label']}"
        row['projekt'] = PROJEKT_HYA
        out.append(row)
    return out


def _fetch_meta():
    stavy_mod, sektory = [], list(KlientSektor.objects.all())
    stavy_hya = []
    try:
        meta = api_meta()
        stavy_mod = meta.get('stavy', [])
        if not sektory:
            for s in meta.get('sektory', []):
                KlientSektor.objects.update_or_create(
                    remote_id=s['id'],
                    defaults={'nazev': s['nazev'], 'razeni': s.get('razeni', 100)},
                )
            sektory = list(KlientSektor.objects.all())
    except ModernikApiError:
        pass
    try:
        meta_h = meta_statuses()
        stavy_hya = [{'kod': s['value'], 'label': s['label']} for s in meta_h.get('statuses', [])]
    except HyaApiError:
        pass
    return stavy_mod, stavy_hya, sektory


def _collect_rows(projekt, q, stav, sektor):
    rows = []
    if projekt in ('', PROJEKT_MODERNIK):
        qs = KlientModernik.objects.all()
        if q:
            qs = qs.filter(
                Q(jmeno__icontains=q)
                | Q(email__icontains=q)
                | Q(telefon__icontains=q)
                | Q(ico__icontains=q)
                | Q(sektor_nazev__icontains=q)
            )
        if stav:
            qs = qs.filter(stav=stav)
        if sektor.isdigit():
            qs = qs.filter(sektor_remote_id=int(sektor))
        for k in qs:
            rows.append({
                'projekt': PROJEKT_MODERNIK,
                'projekt_label': PROJEKT_MAP[PROJEKT_MODERNIK],
                'pk': k.pk,
                'jmeno': k.jmeno,
                'email': k.email,
                'telefon': k.telefon,
                'stav': k.stav,
                'stav_label': k.stav_label,
                'extra': k.sektor_nazev,
                'remote_upraveno': k.remote_upraveno,
            })
    if projekt in ('', PROJEKT_HYA):
        qs = KlientHya.objects.all()
        if q:
            qs = qs.filter(
                Q(jmeno__icontains=q)
                | Q(email__icontains=q)
                | Q(telefon__icontains=q)
                | Q(lokalita__icontains=q)
                | Q(zdroj__icontains=q)
            )
        if stav:
            qs = qs.filter(stav=stav)
        for k in qs:
            rows.append({
                'projekt': PROJEKT_HYA,
                'projekt_label': PROJEKT_MAP[PROJEKT_HYA],
                'pk': k.pk,
                'jmeno': k.jmeno,
                'email': k.email,
                'telefon': k.telefon,
                'stav': k.stav,
                'stav_label': k.stav_label,
                'extra': k.lokalita,
                'remote_upraveno': k.remote_upraveno,
            })
    rows.sort(key=lambda r: r['remote_upraveno'], reverse=True)
    return rows


@login_required_view
def klienti_seznam(request):
    try:
        maybe_auto_nocni_sync()
    except (ModernikApiError, HyaApiError):
        pass
    projekt = (request.GET.get('projekt') or '').strip()
    if projekt not in ('', PROJEKT_MODERNIK, PROJEKT_HYA):
        projekt = ''
    q = (request.GET.get('q') or '').strip()
    stav = (request.GET.get('stav') or '').strip()
    sektor = (request.GET.get('sektor') or '').strip()
    try:
        per_page = int(request.GET.get('per_page') or 25)
    except ValueError:
        per_page = 25
    if per_page not in PER_PAGE:
        per_page = 25
    stavy_mod, stavy_hya, sektory = _fetch_meta()
    stavy = _load_stavy(projekt, stavy_mod, stavy_hya)
    rows = _collect_rows(projekt, q, stav, sektor)
    page = Paginator(rows, per_page).get_page(request.GET.get('stranka') or 1)
    sync_mod = KlientSyncMeta.objects.filter(pk=SYNC_META_MODERNIK).first()
    sync_hya = KlientSyncMeta.objects.filter(pk=SYNC_META_HYA).first()
    prazdna_cache = not KlientModernik.objects.exists() and not KlientHya.objects.exists()
    return render(request, 'klienti_seznam.html', {
        'stranka': page,
        'filtry': {'q': q, 'stav': stav, 'sektor': sektor, 'per_page': per_page, 'projekt': projekt},
        'stavy': stavy,
        'stavy_mod': stavy_mod,
        'stavy_hya': stavy_hya,
        'sektory': sektory,
        'projekty': PROJEKTY,
        'prazdna_cache': prazdna_cache,
        'sync_mod': sync_mod,
        'sync_hya': sync_hya,
    })


@login_required_view
@require_POST
def klienti_sync(request):
    bootstrap_if_empty()
    stats = synchronizuj_klienty()
    m, h = stats['modernik'], stats['hya']
    if m.get('ok'):
        messages.success(
            request,
            f'Moderník: {m.get("updated", 0)} změn, {m.get("deleted", 0)} smazaných v cache.',
        )
    else:
        messages.error(request, f'Moderník: {m.get("error", "chyba")}')
    if h.get('ok'):
        messages.success(
            request,
            f'HereYouAre: {h.get("updated", 0)} změn, {h.get("deleted", 0)} smazaných v cache.',
        )
    else:
        messages.warning(request, f'HereYouAre: {h.get("error", "chyba")}')
    return redirect('klienti')


@login_required_view
@require_http_methods(['GET', 'POST'])
def klient_novy(request):
    projekt = (request.GET.get('projekt') or request.POST.get('projekt') or PROJEKT_MODERNIK).strip()
    if projekt not in (PROJEKT_MODERNIK, PROJEKT_HYA):
        projekt = PROJEKT_MODERNIK
    stavy_mod, stavy_hya, sektory = _fetch_meta()
    stavy = stavy_mod if projekt == PROJEKT_MODERNIK else stavy_hya
    initial = {'projekt': projekt}
    if request.method == 'POST':
        if not _crm_zapis_povolen(projekt):
            return _odmitnout_zapis(request, projekt)
        try:
            if projekt == PROJEKT_HYA:
                body = {
                    'company_name': request.POST.get('jmeno', ''),
                    'contact_name': request.POST.get('kontakt_jmeno', ''),
                    'email': request.POST.get('email', ''),
                    'phone': request.POST.get('telefon', ''),
                    'web': request.POST.get('web', ''),
                    'location': request.POST.get('lokalita', ''),
                    'source': request.POST.get('zdroj', ''),
                    'note': request.POST.get('poznamka', ''),
                    'status': request.POST.get('stav', '') or 'lead_before_web',
                    'has_website': request.POST.get('ma_web') or None,
                    'has_booking_system': request.POST.get('ma_rezervace') or None,
                }
                resp = hya_vytvorit(body)
                klient = _apply_hya(request, resp, 'Klient je založený v HereYouAre.')
            else:
                body = {
                    'jmeno': request.POST.get('jmeno', ''),
                    'email': request.POST.get('email', ''),
                    'telefon': request.POST.get('telefon', ''),
                    'web': request.POST.get('web', ''),
                    'adresa': request.POST.get('adresa', ''),
                    'ico': request.POST.get('ico', ''),
                    'poznamka': request.POST.get('poznamka', ''),
                    'stav': request.POST.get('stav', ''),
                    'sektor_id': request.POST.get('sektor_id') or None,
                    'zmenil': _kdo(request),
                }
                resp = api_vytvorit(body)
                klient = _apply_modernik(request, resp, 'Klient je založený v Moderníku.')
            return redirect('klient_detail', projekt=projekt, pk=klient.pk)
        except (ModernikApiError, HyaApiError) as exc:
            messages.error(request, str(exc))
            initial = request.POST.dict()
    return render(request, 'klienti_form.html', {
        'novy': True,
        'klient': None,
        'initial': initial,
        'stavy': stavy,
        'sektory': sektory,
        'projekt': projekt,
        'projekty': PROJEKTY,
    })


@login_required_view
def klient_detail_redirect(request, pk):
    return redirect('klient_detail', projekt=PROJEKT_MODERNIK, pk=pk)


@login_required_view
@require_http_methods(['GET', 'POST'])
def klient_detail(request, projekt, pk):
    lokal = _lokal(projekt, pk)
    historie = []
    stavy_mod, stavy_hya, sektory = _fetch_meta()
    stavy = stavy_mod if projekt == PROJEKT_MODERNIK else stavy_hya
    if request.method == 'POST':
        if not _crm_zapis_povolen(projekt):
            return _odmitnout_zapis(request, projekt)
        try:
            if projekt == PROJEKT_HYA:
                body = {
                    'updated_on': lokal.remote_upraveno.isoformat(),
                    'company_name': request.POST.get('jmeno', ''),
                    'contact_name': request.POST.get('kontakt_jmeno', ''),
                    'email': request.POST.get('email', ''),
                    'phone': request.POST.get('telefon', ''),
                    'web': request.POST.get('web', ''),
                    'location': request.POST.get('lokalita', ''),
                    'source': request.POST.get('zdroj', ''),
                    'note': request.POST.get('poznamka', ''),
                    'status': request.POST.get('stav', ''),
                    'has_website': request.POST.get('ma_web') or None,
                    'has_booking_system': request.POST.get('ma_rezervace') or None,
                }
                resp = hya_upravit(lokal.remote_id, body)
                klient = _apply_hya(request, resp, 'Uloženo v HereYouAre.')
            else:
                body = {
                    'jmeno': request.POST.get('jmeno', ''),
                    'email': request.POST.get('email', ''),
                    'telefon': request.POST.get('telefon', ''),
                    'web': request.POST.get('web', ''),
                    'adresa': request.POST.get('adresa', ''),
                    'ico': request.POST.get('ico', ''),
                    'poznamka': request.POST.get('poznamka', ''),
                    'stav': request.POST.get('stav', ''),
                    'sektor_id': request.POST.get('sektor_id') or None,
                    'expected_upraveno': lokal.remote_upraveno.isoformat(),
                    'zmenil': _kdo(request),
                }
                resp = api_upravit(lokal.remote_id, body)
                klient = _apply_modernik(request, resp, 'Uloženo v Moderníku.')
            return redirect('klient_detail', projekt=projekt, pk=klient.pk)
        except ModernikApiError as exc:
            _conflict_modernik(request, exc)
            lokal.refresh_from_db()
        except HyaApiError as exc:
            _conflict_hya(request, exc)
            lokal.refresh_from_db()
    if projekt == PROJEKT_MODERNIK:
        try:
            resp = api_detail(lokal.remote_id)
            if resp.get('kontakt'):
                upsert_klient(resp['kontakt'])
                lokal.refresh_from_db()
            historie = resp.get('stav_historie', [])
            _sync_historie(lokal, historie)
        except ModernikApiError as exc:
            messages.warning(request, f'Detail z Moderníku: {exc}')
    else:
        try:
            resp = hya_detail(lokal.remote_id)
            if resp.get('client'):
                upsert_klient_hya(resp['client'])
                lokal.refresh_from_db()
        except HyaApiError as exc:
            messages.warning(request, f'Detail z HYA: {exc}')
    kal_udalosti = (
        klient_udalosti_modernik(lokal) if projekt == PROJEKT_MODERNIK else klient_udalosti_hya(lokal)
    )
    return render(request, 'klienti_detail.html', {
        'klient': lokal,
        'projekt': projekt,
        'projekt_label': PROJEKT_MAP[projekt],
        'historie': lokal.stav_historie.all() if projekt == PROJEKT_MODERNIK else [],
        'stavy': stavy,
        'sektory': sektory,
        'kalendar_udalosti': kal_udalosti,
    })


@login_required_view
@require_POST
def klient_stav(request, projekt, pk):
    lokal = _lokal(projekt, pk)
    if not _crm_zapis_povolen(projekt):
        return _odmitnout_zapis(request, projekt)
    stav = (request.POST.get('stav') or '').strip()
    try:
        if projekt == PROJEKT_HYA:
            resp = hya_zmenit_stav(
                lokal.remote_id,
                {'status': stav, 'updated_on': lokal.remote_upraveno.isoformat()},
            )
            _apply_hya(request, resp, 'Stav uložen v HereYouAre.')
        else:
            resp = api_zmenit_stav(
                lokal.remote_id,
                {
                    'stav': stav,
                    'expected_upraveno': lokal.remote_upraveno.isoformat(),
                    'zmenil': _kdo(request),
                },
            )
            _apply_modernik(request, resp, 'Stav uložen v Moderníku.')
    except ModernikApiError as exc:
        _conflict_modernik(request, exc)
    except HyaApiError as exc:
        _conflict_hya(request, exc)
    qs = request.POST.get('back_qs', '')
    url = reverse('klienti')
    return redirect(f'{url}?{qs}' if qs else url)
