import json
import urllib.error
import urllib.request

from django.conf import settings


class UlovAuthError(Exception):
    def __init__(self, detail='Přihlášení se nepovedlo.'):
        self.detail = detail
        super().__init__(detail)


def ulov_session(email, password):
    base = (getattr(settings, 'ULOV_API_URL', '') or '').rstrip('/')
    key = (getattr(settings, 'MATERIALNIK_M2M_KEY', '') or '').strip()
    if not base:
        raise UlovAuthError('Chybí napojení na účet Ulov.')
    url = f'{base}/api/integrations/v1/materialnik/session'
    body = json.dumps({'email': email, 'password': password}).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-Ulov-M2M-Key': key,
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise UlovAuthError('Nesprávný e-mail nebo heslo.') from exc
        raise UlovAuthError('Přihlášení teď nelze ověřit.') from exc
    except urllib.error.URLError as exc:
        raise UlovAuthError('Přihlášení teď nelze ověřit.') from exc


def ulov_catalog(tenant_uuid):
    base = (getattr(settings, 'ULOV_API_URL', '') or '').rstrip('/')
    key = (getattr(settings, 'MATERIALNIK_M2M_KEY', '') or '').strip()
    if not base:
        return []
    url = f'{base}/api/integrations/v1/materialnik/catalog?tenant_uuid={tenant_uuid}'
    req = urllib.request.Request(
        url,
        headers={'Accept': 'application/json', 'X-Ulov-M2M-Key': key},
        method='GET',
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return data.get('services') or []
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError):
        return []
