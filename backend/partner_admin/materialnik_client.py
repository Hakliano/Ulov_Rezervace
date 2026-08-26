"""HTTP klient FLOW → Materiálník. Krátký timeout, nikdy neshazuje rezervace."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)


class MaterialnikUnavailable(Exception):
    def __init__(self, detail='Materiálník teď neodpovídá.'):
        self.detail = detail
        super().__init__(detail)


class MaterialnikRejected(Exception):
    def __init__(self, detail, status_code=400):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def _base_url():
    return (getattr(settings, 'MATERIALNIK_URL', '') or '').rstrip('/')


def _m2m_key():
    return (getattr(settings, 'MATERIALNIK_M2M_KEY', '') or '').strip()


def _request(method, path, payload=None, timeout=3):
    if getattr(settings, 'MATERIALNIK_STUB', False):
        return _stub(method, path, payload)

    base = _base_url()
    if not base:
        raise MaterialnikUnavailable('Materiálník není nakonfigurován (MATERIALNIK_URL).')

    url = f'{base}{path}'
    body = None
    headers = {
        'Accept': 'application/json',
        'X-Ulov-M2M-Key': _m2m_key(),
    }
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        headers['Content-Type'] = 'application/json; charset=utf-8'

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode('utf-8') or '{}'
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        detail = _http_detail(exc)
        if exc.code >= 500:
            raise MaterialnikUnavailable(detail) from exc
        raise MaterialnikRejected(detail, status_code=exc.code) from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        logger.warning('Materiálník request selhal: %s %s (%s)', method, path, exc)
        raise MaterialnikUnavailable() from exc


def _http_detail(exc):
    try:
        raw = exc.read().decode('utf-8')
        data = json.loads(raw)
        return data.get('detail') or data.get('error') or 'Požadavek Materiálník odmítl.'
    except Exception:  # noqa: BLE001
        return 'Požadavek Materiálník odmítl.'


def _stub(method, path, payload):
    if path.endswith('/provision') or path.endswith('/tenants'):
        return {'status': 'active', 'hmac_key': 'stub-hmac-key'}
    if '/deactivate' in path:
        return {'status': 'inactive'}
    if path.endswith('/consume-preview') or '/spotreba-navrh' in path:
        return {'lines': payload.get('services', []) if payload else [], 'empty': True}
    if path.endswith('/consume') or path.endswith('/events'):
        return {'ok': True, 'duplicate': False}
    return {'ok': True}


def provision_tenant(*, tenant_uuid, salon_id, name):
    return _request(
        'POST',
        '/v1/internal/tenants',
        {
            'tenant_uuid': str(tenant_uuid),
            'external_tenant_id': f'salon:{salon_id}',
            'name': name,
            'source': 'modernik-flow',
        },
        timeout=5,
    )


def deactivate_tenant(*, tenant_uuid):
    return _request(
        'POST',
        f'/v1/internal/tenants/{tenant_uuid}/deactivate',
        {},
        timeout=5,
    )


def consume_preview(*, tenant_uuid, hmac_key, payload):
    return _request(
        'POST',
        '/v1/internal/consume-preview',
        {
            'tenant_uuid': str(tenant_uuid),
            'hmac_key': hmac_key,
            **payload,
        },
        timeout=3,
    )


def confirm_consume(*, tenant_uuid, hmac_key, payload):
    return _request(
        'POST',
        '/v1/internal/consume',
        {
            'tenant_uuid': str(tenant_uuid),
            'hmac_key': hmac_key,
            **payload,
        },
        timeout=3,
    )


def post_event(*, payload, hmac_key, event_id, timestamp):
    """Outbox worker — podepsaný provozní event. Timeout krátký, retry jinde."""
    if getattr(settings, 'MATERIALNIK_STUB', False):
        return {'ok': True, 'duplicate': False}

    base = _base_url()
    if not base:
        raise MaterialnikUnavailable('Materiálník není nakonfigurován (MATERIALNIK_URL).')

    import hashlib
    import hmac

    body = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    msg = f'{timestamp}.{event_id}.'.encode('utf-8') + body
    signature = hmac.new(hmac_key.encode('utf-8'), msg, hashlib.sha256).hexdigest()
    url = f'{base}/v1/events'
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json; charset=utf-8',
        'X-Timestamp': timestamp,
        'X-Key-Id': 'tenant',
        'X-Signature': signature,
    }
    req = urllib.request.Request(url, data=body, headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            raw = resp.read().decode('utf-8') or '{}'
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        detail = _http_detail(exc)
        if exc.code >= 500:
            raise MaterialnikUnavailable(detail) from exc
        raise MaterialnikRejected(detail, status_code=exc.code) from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise MaterialnikUnavailable() from exc
