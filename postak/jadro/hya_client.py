"""HTTP klient na HereYouAre interní postak API."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings


class HyaApiError(Exception):
    def __init__(self, message, *, status=0, code='', payload=None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.payload = payload or {}


def _base():
    base = (getattr(settings, 'HYA_API_BASE', '') or '').strip().rstrip('/')
    if not base:
        raise HyaApiError('Není nastavena HYA_API_BASE.')
    return base


def _token():
    token = (getattr(settings, 'HYA_POSTAK_API_TOKEN', '') or '').strip()
    if not token:
        raise HyaApiError('Není nastaven HYA_POSTAK_API_TOKEN.')
    return token


def _request(method, path, *, query=None, body=None, timeout=30):
    url = _base() + path
    if query:
        qs = urllib.parse.urlencode({k: v for k, v in query.items() if v is not None and v != ''})
        if qs:
            url = f'{url}?{qs}'
    data = None
    headers = {
        'Authorization': f'Bearer {_token()}',
        'Accept': 'application/json',
    }
    if body is not None:
        data = json.dumps(body).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode('utf-8')
            payload = json.loads(raw) if raw else {}
            if payload.get('ok') is False:
                raise HyaApiError(payload.get('error') or 'Chyba API', status=resp.status, payload=payload)
            return payload
    except urllib.error.HTTPError as exc:
        payload = {}
        try:
            payload = json.loads(exc.read().decode('utf-8'))
        except Exception:
            pass
        detail = payload.get('error') or exc.reason or 'Chyba API'
        code = 'conflict' if exc.code == 409 else payload.get('code', '')
        raise HyaApiError(detail, status=exc.code, code=code, payload=payload) from exc
    except urllib.error.URLError as exc:
        raise HyaApiError('HereYouAre API není dostupné.') from exc


def seznam(**params):
    return _request('GET', '/prospects/', query=params)


def detail(pk):
    return _request('GET', f'/prospects/{pk}/')


def vytvorit(data):
    return _request('POST', '/prospects/', body=data)


def upravit(pk, data):
    return _request('PATCH', f'/prospects/{pk}/', body=data)


def zmenit_stav(pk, data):
    return _request('PATCH', f'/prospects/{pk}/status/', body=data)


def zmeny(*, since, limit=500):
    return _request('GET', '/prospects/changes/', query={'since': since, 'limit': limit})


def smazane(*, since, limit=500):
    return _request('GET', '/prospects/deletions/', query={'since': since, 'limit': limit})


def meta_statuses():
    return _request('GET', '/meta/statuses/')
