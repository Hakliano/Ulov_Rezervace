import json
import logging
import urllib.error
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)


class UlovAuthError(Exception):
    def __init__(self, detail='Přihlášení se nepovedlo.'):
        self.detail = detail
        super().__init__(detail)


def _ulov_headers(**extra):
    key = (getattr(settings, 'MATERIALNIK_M2M_KEY', '') or '').strip()
    headers = {
        'Accept': 'application/json',
        'X-Ulov-M2M-Key': key,
        **extra,
    }
    host = (getattr(settings, 'ULOV_API_HOST', '') or '').strip()
    if host:
        headers['Host'] = host
    # LIVE má SECURE_SSL_REDIRECT — bez této hlavičky interní HTTP skončí 301 na HTTPS.
    if (getattr(settings, 'ULOV_API_URL', '') or '').startswith('http://'):
        headers.setdefault('X-Forwarded-Proto', 'https')
    return headers


def _ulov_request(url, *, data=None, method='GET', extra_headers=None):
    headers = _ulov_headers(**(extra_headers or {}))
    host = headers.pop('Host', None)
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    if host:
        req.add_unredirected_header('Host', host)
    return urllib.request.urlopen(req, timeout=5)


def ulov_session(email, password):
    base = (getattr(settings, 'ULOV_API_URL', '') or '').rstrip('/')
    if not base:
        raise UlovAuthError('Chybí napojení na účet Ulov.')
    url = f'{base}/api/integrations/v1/materialnik/session'
    body = json.dumps({'email': email, 'password': password}).encode('utf-8')
    try:
        with _ulov_request(
            url, data=body, method='POST',
            extra_headers={'Content-Type': 'application/json'},
        ) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        logger.warning('ulov_session HTTP %s', exc.code)
        if exc.code in (401, 403):
            raise UlovAuthError('Nesprávný e-mail nebo heslo.') from exc
        raise UlovAuthError('Přihlášení teď nelze ověřit.') from exc
    except urllib.error.URLError as exc:
        logger.warning('ulov_session URL error: %s', exc)
        raise UlovAuthError('Přihlášení teď nelze ověřit.') from exc


def ulov_catalog(tenant_uuid):
    base = (getattr(settings, 'ULOV_API_URL', '') or '').rstrip('/')
    if not base:
        return []
    url = f'{base}/api/integrations/v1/materialnik/catalog?tenant_uuid={tenant_uuid}'
    try:
        with _ulov_request(url, method='GET') as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return data.get('services') or []
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError):
        return []
