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


def _adresni_z_api(data: dict) -> dict:
    from .partner_import import normalizuj_souradnice

    out = {}
    if 'adresa' in data:
        raw = data.get('adresa')
        out['adresa'] = raw if raw not in (None, '') else None
    if 'mesto' in data:
        out['mesto'] = (data.get('mesto') or '').strip()[:120] or None
    if 'cast_obce' in data:
        out['cast_obce'] = (data.get('cast_obce') or '').strip()[:120] or None
    if 'latitude' in data or 'longitude' in data:
        lat_in = data.get('latitude') if 'latitude' in data else None
        lon_in = data.get('longitude') if 'longitude' in data else None
        lat, lon = normalizuj_souradnice(lat_in, lon_in)
        out['latitude'] = lat
        out['longitude'] = lon
    return out


def _kontakt_json(kontakt: PotencialniKontakt) -> dict:
    return {
        'id': kontakt.id,
        'jmeno': kontakt.jmeno,
        'email': kontakt.email,
        'telefon': kontakt.telefon or '',
        'web': kontakt.web or '',
        'adresa': kontakt.adresa or '',
        'mesto': kontakt.mesto or '',
        'cast_obce': kontakt.cast_obce or '',
        'latitude': str(kontakt.latitude) if kontakt.latitude is not None else '',
        'longitude': str(kontakt.longitude) if kontakt.longitude is not None else '',
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


def _kontakt_field_json(kontakt, field: str):
    if field == 'sektor_id':
        return kontakt.sektor_id
    if field in ('latitude', 'longitude'):
        val = getattr(kontakt, field)
        return '' if val is None else str(val)
    if field == 'stav':
        return kontakt.stav
    return getattr(kontakt, field) or ''


def _field_conflict(kontakt, data: dict):
    expected = data.get('expected_fields')
    if not isinstance(expected, dict):
        return None
    conflicts = []
    for field, exp_val in expected.items():
        if field not in data:
            continue
        cur = _kontakt_field_json(kontakt, field)
        exp_norm = '' if exp_val is None else exp_val
        cur_norm = '' if cur is None else cur
        if str(cur_norm).strip() != str(exp_norm).strip():
            conflicts.append(field)
    if not conflicts:
        return None
    return JsonResponse({
        'ok': False,
        'code': 'conflict',
        'detail': 'Konflikt u polí: ' + ', '.join(conflicts),
        'fields': conflicts,
        'kontakt': _kontakt_json(kontakt),
    }, status=409)


_PATCH_META = frozenset({'expected_upraveno', 'expected_fields', 'zmenil'})


def _aplikuj_patch(kontakt, data: dict, stary_stav: str):
    """Použije jen klíče přítomné v data. Vrací JsonResponse chyby nebo None."""
    jmeno_in = 'jmeno' in data
    email_in = 'email' in data
    jmeno = (data.get('jmeno') if jmeno_in else kontakt.jmeno) or ''
    jmeno = jmeno.strip()
    email = (data.get('email') if email_in else kontakt.email) or ''
    email = email.strip().lower()
    if jmeno_in or email_in:
        if not jmeno or not email:
            return JsonResponse({'ok': False, 'detail': 'Jméno a e-mail jsou povinné.'}, status=400)
        if PotencialniKontakt.objects.exclude(pk=kontakt.pk).filter(email=email).exists():
            return JsonResponse({'ok': False, 'detail': 'E-mail už používá jiný záznam.'}, status=400)
        try:
            validate_email(email)
        except ValidationError:
            return JsonResponse({'ok': False, 'detail': 'Neplatný e-mail.'}, status=400)
    if jmeno_in:
        kontakt.jmeno = jmeno[:200]
    if email_in:
        kontakt.email = email
    if 'telefon' in data:
        kontakt.telefon = ('' if data['telefon'] is None else (data.get('telefon') or ''))[:200]
    if 'web' in data:
        kontakt.web = ('' if data['web'] is None else (data.get('web') or ''))[:400]
    if 'ico' in data:
        kontakt.ico = ('' if data['ico'] is None else (data.get('ico') or ''))[:20]
    if 'poznamka' in data:
        kontakt.poznamka = '' if data['poznamka'] is None else (data.get('poznamka') or '')
    adresni_in = {k: data[k] for k in ('adresa', 'mesto', 'cast_obce', 'latitude', 'longitude') if k in data}
    if adresni_in:
        for fld, val in _adresni_z_api(adresni_in).items():
            setattr(kontakt, fld, val)
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
    return None


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
    mesto = (request.GET.get('mesto') or '').strip()
    if mesto:
        qs = qs.filter(mesto__icontains=mesto)
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
    create_kwargs = {
        'jmeno': jmeno[:200],
        'email': email,
        'telefon': (data.get('telefon') or '')[:200],
        'web': (data.get('web') or '')[:400],
        'ico': (data.get('ico') or '')[:20],
        'poznamka': (data.get('poznamka') or ''),
        'sektor': sektor,
        'stav': stav,
    }
    if any(k in data for k in ('adresa', 'mesto', 'cast_obce', 'latitude', 'longitude')):
        create_kwargs.update(_adresni_z_api(data))
    else:
        create_kwargs['adresa'] = (data.get('adresa') or '') or None
    kontakt = PotencialniKontakt.objects.create(**create_kwargs)
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
    if request.method == 'DELETE':
        kontakt_id = kontakt.id
        PotencialniKontaktTombstone.objects.update_or_create(
            kontakt_id=kontakt_id,
            defaults={'smazano': timezone.now()},
        )
        kontakt.delete()
        return JsonResponse({'ok': True, 'deleted_id': kontakt_id})
    patch_data = {k: v for k, v in data.items() if k not in _PATCH_META}
    if not patch_data:
        return JsonResponse({'ok': False, 'detail': 'Žádné pole k úpravě.'}, status=400)
    if data.get('expected_fields'):
        conflict = _field_conflict(kontakt, data)
    else:
        conflict = _conflict(kontakt, data.get('expected_upraveno'))
    if conflict:
        return conflict
    stary_stav = kontakt.stav
    err = _aplikuj_patch(kontakt, data, stary_stav)
    if err:
        return err
    return JsonResponse({'ok': True, 'kontakt': _kontakt_json(kontakt)})


@csrf_exempt
@postak_api_auth
@require_http_methods(['PATCH'])
def zmena_stavu(request, pk):
    kontakt = get_object_or_404(PotencialniKontakt, pk=pk)
    data = _parse_body(request)
    if data is None:
        return JsonResponse({'ok': False, 'detail': 'Neplatný JSON.'}, status=400)
    body = {'stav': data.get('stav'), 'expected_fields': data.get('expected_fields')}
    if data.get('expected_fields'):
        conflict = _field_conflict(kontakt, body)
    else:
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
    try:
        limit = min(max(int(request.GET.get('limit') or 500), 1), 1000)
        offset = max(int(request.GET.get('offset') or 0), 0)
    except ValueError:
        limit, offset = 500, 0
    qs = PotencialniKontakt.objects.select_related('sektor')
    if since:
        qs = qs.filter(upraveno__gt=since).order_by('upraveno', 'pk')
    else:
        qs = qs.order_by('pk')
    total = qs.count()
    page = list(qs[offset:offset + limit])
    items = [_kontakt_json(k) for k in page]
    has_more = offset + len(page) < total
    tomb_qs = PotencialniKontaktTombstone.objects.all()
    if since:
        tomb_qs = tomb_qs.filter(smazano__gt=since)
    tomb_qs = tomb_qs.order_by('smazano', 'kontakt_id')
    deleted = [
        {'id': t.kontakt_id, 'smazano': _iso(t.smazano)}
        for t in tomb_qs[offset:offset + limit]
    ]
    sektory = list(PotencialniSektor.objects.order_by('razeni', 'nazev').values('id', 'nazev', 'razeni'))
    return JsonResponse({
        'ok': True,
        'items': items,
        'deleted': deleted,
        'sektory': sektory,
        'server_time': _iso(timezone.now()),
        'total': total,
        'offset': offset,
        'limit': limit,
        'has_more': has_more,
        'next_offset': offset + len(page) if has_more else offset,
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
