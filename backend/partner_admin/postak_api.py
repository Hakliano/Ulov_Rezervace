"""Interní JSON API pro Pošťák — potenciální klienti Moderníka."""

from __future__ import annotations

import json
from functools import wraps

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.core.validators import validate_email
from django.db.models import Q
from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import PotencialniKontakt, PotencialniKontaktStavHistorie, PotencialniKontaktTombstone, PotencialniSektor
from .potencialni import sektor_podle_nazvu

STAVY = {k for k, _ in PotencialniKontakt.STAVY}
PER_PAGE_OPTS = (25, 50, 100)


def _iso(dt):
    if not dt:
        return ''
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return dt.isoformat()


def _kontakt_json(kontakt: PotencialniKontakt) -> dict:
    return {
        'id': kontakt.id,
        'jmeno': kontakt.jmeno,
        'email': kontakt.email,
        'telefon': kontakt.telefon or '',
        'web': kontakt.web or '',
        'adresa': kontakt.adresa or '',
        'ico': kontakt.ico or '',
        'poznamka': kontakt.poznamka or '',
        'stav': kontakt.stav,
        'stav_label': kontakt.get_stav_display(),
        'sektor_id': kontakt.sektor_id,
        'sektor_nazev': kontakt.sektor.nazev if kontakt.sektor_id else '',
        'vytvoreno': _iso(kontakt.vytvoreno),
        'upraveno': _iso(kontakt.upraveno),
    }


def _token_ok(request) -> bool:
    token = (settings.POSTAK_POTENCIALNI_API_TOKEN or '').strip()
    if not token:
        return False
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        return auth[7:].strip() == token
    return request.headers.get('X-Postak-Token', '').strip() == token


def postak_api_auth(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not _token_ok(request):
            return JsonResponse({'ok': False, 'detail': 'Neplatná autentizace.'}, status=401)
        return view(request, *args, **kwargs)
    return wrapper


def _conflict(kontakt, expected_upraveno):
    if not expected_upraveno:
        return None
    exp = parse_datetime(expected_upraveno)
    if not exp:
        return None
    if timezone.is_naive(exp):
        exp = timezone.make_aware(exp, timezone.get_current_timezone())
    if kontakt.upraveno > exp:
        return JsonResponse({
            'ok': False,
            'code': 'conflict',
            'detail': 'Záznam na Moderníku byl mezitím změněn.',
            'kontakt': _kontakt_json(kontakt),
        }, status=409)


def _zapis_stav_historie(kontakt, stary, novy, kdo=''):
    if stary == novy:
        return
    PotencialniKontaktStavHistorie.objects.create(
        kontakt=kontakt,
        stav_pred=stary or '',
        stav=novy,
        zmenil=(kdo or '')[:120],
    )


def _filtruj(qs, request):
    q = (request.GET.get('q') or '').strip()
    stav = (request.GET.get('stav') or '').strip()
    sektor = (request.GET.get('sektor') or '').strip()
    if q:
        qs = qs.filter(
            Q(jmeno__icontains=q)
            | Q(email__icontains=q)
            | Q(telefon__icontains=q)
            | Q(ico__icontains=q)
        )
    if stav in STAVY:
        qs = qs.filter(stav=stav)
    if sektor.isdigit():
        qs = qs.filter(sektor_id=int(sektor))
    return qs


def _parse_body(request):
    try:
        return json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return None


@csrf_exempt
@postak_api_auth
@require_http_methods(['GET', 'POST'])
def kolekce(request):
    if request.method == 'GET':
        qs = _filtruj(PotencialniKontakt.objects.select_related('sektor'), request)
        try:
            per_page = int(request.GET.get('per_page') or 25)
        except ValueError:
            per_page = 25
        if per_page not in PER_PAGE_OPTS:
            per_page = 25
        page = Paginator(qs, per_page).get_page(request.GET.get('stranka') or 1)
        return JsonResponse({
            'ok': True,
            'items': [_kontakt_json(k) for k in page.object_list],
            'total': page.paginator.count,
            'page': page.number,
            'pages': page.paginator.num_pages,
            'per_page': per_page,
        })
    data = _parse_body(request)
    if data is None:
        return JsonResponse({'ok': False, 'detail': 'Neplatný JSON.'}, status=400)
    jmeno = (data.get('jmeno') or '').strip()
    email = (data.get('email') or '').strip().lower()
    if not jmeno or not email:
        return JsonResponse({'ok': False, 'detail': 'Jméno a e-mail jsou povinné.'}, status=400)
    if PotencialniKontakt.objects.filter(email=email).exists():
        return JsonResponse({'ok': False, 'detail': 'E-mail už existuje.'}, status=400)
    try:
        validate_email(email)
    except ValidationError:
        return JsonResponse({'ok': False, 'detail': 'Neplatný e-mail.'}, status=400)
    sektor_id = data.get('sektor_id')
    sektor = PotencialniSektor.objects.filter(pk=sektor_id).first() if sektor_id else None
    if sektor is None:
        sektor = sektor_podle_nazvu(jmeno)
    stav = (data.get('stav') or PotencialniKontakt.STAV_LEAD_PRED).strip()
    if stav not in STAVY:
        stav = PotencialniKontakt.STAV_LEAD_PRED
    kontakt = PotencialniKontakt.objects.create(
        jmeno=jmeno[:200],
        email=email,
        telefon=(data.get('telefon') or '')[:200],
        web=(data.get('web') or '')[:400],
        adresa=(data.get('adresa') or ''),
        ico=(data.get('ico') or '')[:20],
        poznamka=(data.get('poznamka') or ''),
        sektor=sektor,
        stav=stav,
    )
    _zapis_stav_historie(kontakt, '', stav, data.get('zmenil', ''))
    return JsonResponse({'ok': True, 'kontakt': _kontakt_json(kontakt)}, status=201)


@csrf_exempt
@postak_api_auth
@require_http_methods(['GET', 'PATCH', 'DELETE'])
def detail(request, pk):
    kontakt = get_object_or_404(PotencialniKontakt.objects.select_related('sektor'), pk=pk)
    if request.method == 'GET':
        hist = [
            {
                'stav': h.stav,
                'stav_pred': h.stav_pred,
                'stav_label': dict(PotencialniKontakt.STAVY).get(h.stav, h.stav),
                'kdo': h.zmenil,
                'kdy': _iso(h.vytvoreno),
            }
            for h in kontakt.stav_historie.all()[:30]
        ]
        return JsonResponse({'ok': True, 'kontakt': _kontakt_json(kontakt), 'stav_historie': hist})
    data = _parse_body(request) if request.method != 'GET' else {}
    if data is None and request.method != 'DELETE':
        return JsonResponse({'ok': False, 'detail': 'Neplatný JSON.'}, status=400)
    data = data or {}
    conflict = _conflict(kontakt, data.get('expected_upraveno'))
    if conflict:
        return conflict
    if request.method == 'DELETE':
        kontakt_id = kontakt.id
        PotencialniKontaktTombstone.objects.update_or_create(
            kontakt_id=kontakt_id,
            defaults={'smazano': timezone.now()},
        )
        kontakt.delete()
        return JsonResponse({'ok': True, 'deleted_id': kontakt_id})
    jmeno = (data.get('jmeno') or kontakt.jmeno).strip()
    email = (data.get('email') or kontakt.email).strip().lower()
    if not jmeno or not email:
        return JsonResponse({'ok': False, 'detail': 'Jméno a e-mail jsou povinné.'}, status=400)
    if PotencialniKontakt.objects.exclude(pk=pk).filter(email=email).exists():
        return JsonResponse({'ok': False, 'detail': 'E-mail už používá jiný záznam.'}, status=400)
    try:
        validate_email(email)
    except ValidationError:
        return JsonResponse({'ok': False, 'detail': 'Neplatný e-mail.'}, status=400)
    stary_stav = kontakt.stav
    kontakt.jmeno = jmeno[:200]
    kontakt.email = email
    kontakt.telefon = (data.get('telefon') if 'telefon' in data else kontakt.telefon)[:200]
    kontakt.web = (data.get('web') if 'web' in data else kontakt.web)[:400]
    kontakt.adresa = data.get('adresa') if 'adresa' in data else kontakt.adresa
    kontakt.ico = (data.get('ico') if 'ico' in data else kontakt.ico)[:20]
    kontakt.poznamka = data.get('poznamka') if 'poznamka' in data else kontakt.poznamka
    if 'sektor_id' in data:
        sid = data.get('sektor_id')
        kontakt.sektor = PotencialniSektor.objects.filter(pk=sid).first() if sid else None
    if 'stav' in data:
        novy = (data.get('stav') or '').strip()
        if novy in STAVY:
            kontakt.stav = novy
    kontakt.save()
    if 'stav' in data:
        _zapis_stav_historie(kontakt, stary_stav, kontakt.stav, data.get('zmenil', ''))
    kontakt.refresh_from_db()
    return JsonResponse({'ok': True, 'kontakt': _kontakt_json(kontakt)})


@csrf_exempt
@postak_api_auth
@require_http_methods(['PATCH'])
def zmena_stavu(request, pk):
    kontakt = get_object_or_404(PotencialniKontakt, pk=pk)
    data = _parse_body(request)
    if data is None:
        return JsonResponse({'ok': False, 'detail': 'Neplatný JSON.'}, status=400)
    conflict = _conflict(kontakt, data.get('expected_upraveno'))
    if conflict:
        return conflict
    stav = (data.get('stav') or '').strip()
    if stav not in STAVY:
        return JsonResponse({'ok': False, 'detail': 'Neznámý stav.'}, status=400)
    stary = kontakt.stav
    kontakt.stav = stav
    kontakt.save(update_fields=['stav', 'upraveno'])
    _zapis_stav_historie(kontakt, stary, stav, data.get('zmenil', ''))
    kontakt.refresh_from_db()
    return JsonResponse({'ok': True, 'kontakt': _kontakt_json(kontakt)})


@csrf_exempt
@postak_api_auth
@require_http_methods(['GET'])
def zmeny(request):
    since_raw = (request.GET.get('since') or '').strip()
    since = parse_datetime(since_raw) if since_raw else None
    if since and timezone.is_naive(since):
        since = timezone.make_aware(since, timezone.get_current_timezone())
    qs = PotencialniKontakt.objects.select_related('sektor')
    if since:
        qs = qs.filter(upraveno__gt=since)
    try:
        limit = min(max(int(request.GET.get('limit') or 500), 1), 1000)
    except ValueError:
        limit = 500
    items = [_kontakt_json(k) for k in qs.order_by('upraveno')[:limit]]
    tomb_qs = PotencialniKontaktTombstone.objects.all()
    if since:
        tomb_qs = tomb_qs.filter(smazano__gt=since)
    deleted = [{'id': t.kontakt_id, 'smazano': _iso(t.smazano)} for t in tomb_qs.order_by('smazano')[:limit]]
    sektory = list(PotencialniSektor.objects.order_by('razeni', 'nazev').values('id', 'nazev', 'razeni'))
    return JsonResponse({
        'ok': True,
        'items': items,
        'deleted': deleted,
        'sektory': sektory,
        'server_time': _iso(timezone.now()),
    })


@csrf_exempt
@postak_api_auth
@require_http_methods(['GET'])
def stavy_a_sektory(request):
    return JsonResponse({
        'ok': True,
        'stavy': [{'kod': k, 'label': l} for k, l in PotencialniKontakt.STAVY],
        'sektory': list(PotencialniSektor.objects.order_by('razeni', 'nazev').values('id', 'nazev', 'razeni')),
    })
