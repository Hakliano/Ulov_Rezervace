"""HTTP klient na Moderník partner-admin API."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings


class ModernikApiError(Exception):
    def __init__(self, message, *, status=0, code='', payload=None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.payload = payload or {}


def _base():
    base = (getattr(settings, 'MODERNIK_API_BASE', '') or '').strip().rstrip('/')
    if not base:
        raise ModernikApiError('Není nastavena MODERNIK_API_BASE.')
    return base


def _token():
    token = (getattr(settings, 'MODERNIK_API_TOKEN', '') or '').strip()
    if not token:
        raise ModernikApiError('Není nastaven MODERNIK_API_TOKEN.')
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
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        payload = {}
        try:
            payload = json.loads(exc.read().decode('utf-8'))
        except Exception:
            pass
        detail = payload.get('detail') or exc.reason or 'Chyba API'
        raise ModernikApiError(detail, status=exc.code, code=payload.get('code', ''), payload=payload) from exc
    except urllib.error.URLError as exc:
        raise ModernikApiError('Moderník API není dostupné.') from exc


def seznam(**params):
    return _request('GET', '/potencialni/', query=params)


def detail(pk):
    return _request('GET', f'/potencialni/{pk}/')


def vytvorit(data):
    return _request('POST', '/potencialni/', body=data)


def upravit(pk, data):
    return _request('PATCH', f'/potencialni/{pk}/', body=data)


def zmenit_stav(pk, data):
    return _request('PATCH', f'/potencialni/{pk}/stav/', body=data)


def smazat(pk, data):
    return _request('DELETE', f'/potencialni/{pk}/', body=data)


def zmeny(since=None, limit=500):
    q = {'limit': limit}
    if since:
        q['since'] = since
    return _request('GET', '/potencialni/zmeny/', query=q)


def meta():
    return _request('GET', '/potencialni/meta/')
