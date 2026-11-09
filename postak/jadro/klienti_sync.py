"""Synchronizace lokální cache klientů Moderníku a HereYouAre."""

from __future__ import annotations

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .hya_client import HyaApiError, meta_statuses, seznam as hya_seznam, smazane as hya_smazane, zmeny as hya_zmeny
from .klienti_constants import SYNC_META_HYA, SYNC_META_MODERNIK
from .klienti_models import KlientHya, KlientModernik, KlientSektor, KlientSyncMeta
from .modernik_client import ModernikApiError, seznam, zmeny

_HYA_LABELS: dict[str, str] = {}


def _meta(pk):
    row, _ = KlientSyncMeta.objects.get_or_create(pk=pk)
    return row


def _stav_label_hya(code):
    if not code:
        return ''
    if code in _HYA_LABELS:
        return _HYA_LABELS[code]
    try:
        meta = meta_statuses()
        for row in meta.get('statuses', []):
            _HYA_LABELS[row['value']] = row['label']
    except HyaApiError:
        pass
    return _HYA_LABELS.get(code, code)[:80]


def _tri_cache(val):
    if val is True:
        return 'yes'
    if val is False:
        return 'no'
    return 'unknown'


def upsert_klient(item):
    upr = parse_datetime(item.get('upraveno') or '') or timezone.now()
    KlientModernik.objects.update_or_create(
        remote_id=item['id'],
        defaults={
            'jmeno': item.get('jmeno', '')[:200],
            'email': item.get('email', '')[:254],
            'telefon': item.get('telefon', '')[:200],
            'web': item.get('web', '')[:400],
            'adresa': item.get('adresa', ''),
            'ico': item.get('ico', '')[:20],
            'poznamka': item.get('poznamka', ''),
            'stav': item.get('stav', '')[:32],
            'stav_label': item.get('stav_label', '')[:80],
            'sektor_remote_id': item.get('sektor_id'),
            'sektor_nazev': (item.get('sektor_nazev') or '')[:80],
            'remote_upraveno': upr,
        },
    )


def upsert_klient_hya(client):
    upr = parse_datetime(client.get('updated_on') or '') or timezone.now()
    stav = (client.get('status') or '')[:32]
    KlientHya.objects.update_or_create(
        remote_id=client['id'],
        defaults={
            'jmeno': (client.get('company_name') or '')[:200],
            'kontakt_jmeno': (client.get('contact_name') or '')[:200],
            'email': (client.get('email') or '')[:254],
            'telefon': (client.get('phone') or '')[:200],
            'web': (client.get('web') or '')[:400],
            'lokalita': (client.get('location') or '')[:200],
            'zdroj': (client.get('source') or '')[:120],
            'ma_web': _tri_cache(client.get('has_website'))[:12],
            'ma_rezervace': _tri_cache(client.get('has_booking_system'))[:12],
            'poznamka': (client.get('note') or client.get('description') or ''),
            'stav': stav,
            'stav_label': _stav_label_hya(stav),
            'remote_upraveno': upr,
        },
    )


def _sync_sektory(items):
    for s in items or []:
        KlientSektor.objects.update_or_create(
            remote_id=s['id'],
            defaults={'nazev': s['nazev'][:80], 'razeni': s.get('razeni', 100)},
        )


def _delta_modernik(since=None):
    resp = zmeny(since=since)
    for item in resp.get('items', []):
        upsert_klient(item)
    for row in resp.get('deleted', []):
        KlientModernik.objects.filter(remote_id=row['id']).delete()
    _sync_sektory(resp.get('sektory'))
    server_time = parse_datetime(resp.get('server_time') or '') or timezone.now()
    return {'updated': len(resp.get('items', [])), 'deleted': len(resp.get('deleted', [])), 'cursor': server_time}


def _bootstrap_modernik():
    if KlientModernik.objects.exists():
        return False
    page = 1
    while True:
        resp = seznam(stranka=page, per_page=100)
        for item in resp.get('items', []):
            upsert_klient(item)
        if page >= resp.get('pages', 1):
            break
        page += 1
    return True


def synchronizuj_modernik(*, nocni=False):
    meta = _meta(SYNC_META_MODERNIK)
    stats = {'ok': True, 'updated': 0, 'deleted': 0, 'error': ''}
    try:
        _bootstrap_modernik()
        since = meta.posledni_delta.isoformat() if meta.posledni_delta else None
        if since:
            chunk = _delta_modernik(since=since)
        else:
            chunk = {'updated': 0, 'deleted': 0, 'cursor': timezone.now()}
        stats['updated'] = chunk['updated']
        stats['deleted'] = chunk['deleted']
        meta.posledni_delta = chunk['cursor']
        if nocni:
            meta.posledni_nocni = timezone.now()
        meta.posledni_chyba = ''
        meta.save()
    except ModernikApiError as exc:
        meta.posledni_chyba = str(exc)[:300]
        meta.save(update_fields=['posledni_chyba'])
        stats['ok'] = False
        stats['error'] = str(exc)
    return stats


def _bootstrap_hya():
    if KlientHya.objects.exists():
        return False
    page = 1
    while True:
        resp = hya_seznam(page=page, page_size=100)
        for item in resp.get('results', []):
            upsert_klient_hya(item)
        pag = resp.get('pagination') or {}
        if page >= pag.get('total_pages', 1):
            break
        page += 1
    return True


def _delta_hya(since):
    updated = deleted = 0
    cursor = parse_datetime(since) or timezone.now()
    offset = since
    while True:
        resp = hya_zmeny(since=offset, limit=500)
        items = resp.get('results', [])
        for item in items:
            upsert_klient_hya(item)
            upr = parse_datetime(item.get('updated_on') or '')
            if upr and upr > cursor:
                cursor = upr
        updated += len(items)
        if not resp.get('has_more'):
            break
        offset = items[-1]['updated_on'] if items else offset

    offset_del = since
    while True:
        resp = hya_smazane(since=offset_del, limit=500)
        rows = resp.get('deletions', [])
        for row in rows:
            KlientHya.objects.filter(remote_id=row['id']).delete()
            dt = parse_datetime(row.get('deleted_at') or '')
            if dt and dt > cursor:
                cursor = dt
        deleted += len(rows)
        if not resp.get('has_more'):
            break
        offset_del = rows[-1]['deleted_at'] if rows else offset_del

    return {'updated': updated, 'deleted': deleted, 'cursor': cursor}


def synchronizuj_hya(*, nocni=False):
    meta = _meta(SYNC_META_HYA)
    stats = {'ok': True, 'updated': 0, 'deleted': 0, 'error': ''}
    try:
        _bootstrap_hya()
        since = meta.posledni_delta.isoformat() if meta.posledni_delta else None
        if since:
            chunk = _delta_hya(since)
        else:
            chunk = {'updated': 0, 'deleted': 0, 'cursor': timezone.now()}
        stats['updated'] = chunk['updated']
        stats['deleted'] = chunk['deleted']
        meta.posledni_delta = chunk['cursor']
        if nocni:
            meta.posledni_nocni = timezone.now()
        meta.posledni_chyba = ''
        meta.save()
    except HyaApiError as exc:
        meta.posledni_chyba = str(exc)[:300]
        meta.save(update_fields=['posledni_chyba'])
        stats['ok'] = False
        stats['error'] = str(exc)
    return stats


def synchronizuj_klienty(*, nocni=False):
    return {
        'modernik': synchronizuj_modernik(nocni=nocni),
        'hya': synchronizuj_hya(nocni=nocni),
    }


def bootstrap_if_empty():
    return {
        'modernik': _bootstrap_modernik(),
        'hya': _bootstrap_hya(),
    }


def maybe_auto_nocni_sync():
    now = timezone.localtime()
    if now.hour > 6:
        return False
    changed = False
    for pk in (SYNC_META_MODERNIK, SYNC_META_HYA):
        meta = _meta(pk)
        if meta.posledni_nocni and (now - meta.posledni_nocni).total_seconds() < 86400:
            continue
        if meta.posledni_delta and (now - meta.posledni_delta).total_seconds() < 86400:
            continue
        changed = True
    if not changed:
        return False
    synchronizuj_klienty(nocni=True)
    return True
