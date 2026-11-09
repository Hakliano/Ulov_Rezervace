"""Klient Bunny.net Storage — pouze prefix Pošťáka pod postak/."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Iterable

from django.conf import settings


class BunnyStorageError(Exception):
    pass


class BunnyStorageClient:
    def __init__(self, *, zone: str, access_key: str, api_base: str, root_prefix: str):
        self.zone = zone.strip('/')
        self.access_key = access_key.strip()
        self.api_base = api_base.rstrip('/')
        self.root_prefix = root_prefix.strip('/')

    def enabled(self) -> bool:
        return bool(self.zone and self.access_key and self.root_prefix)

    def _sanitize_rel(self, name: str) -> str:
        text = (name or '').replace('\\', '/').lstrip('/')
        parts = [p for p in text.split('/') if p and p != '.']
        if '..' in parts:
            raise BunnyStorageError('Neplatná cesta k souboru.')
        return '/'.join(parts)

    def object_key(self, django_name: str) -> str:
        rel = self._sanitize_rel(django_name)
        full = f'{self.root_prefix}/{rel}' if rel else self.root_prefix
        self._assert_allowed(full)
        return full

    def _assert_allowed(self, full_key: str) -> None:
        root = self.root_prefix
        if full_key != root and not full_key.startswith(root + '/'):
            raise BunnyStorageError('Operace mimo vyhrazený prefix postak.')

    def _url(self, object_key: str) -> str:
        return f'{self.api_base}/{self.zone}/{object_key}'

    def _request(self, method: str, object_key: str, data: bytes | None = None, headers: dict | None = None):
        req = urllib.request.Request(self._url(object_key), data=data, method=method)
        req.add_header('AccessKey', self.access_key)
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            if method == 'HEAD' or method == 'GET':
                if exc.code == 404:
                    return None
            raise BunnyStorageError(f'Bunny HTTP {exc.code}') from exc

    def put(self, django_name: str, data: bytes, content_type: str = 'application/octet-stream') -> str:
        key = self.object_key(django_name)
        self._request('PUT', key, data=data, headers={'Content-Type': content_type})
        return django_name

    def get(self, django_name: str) -> bytes:
        key = self.object_key(django_name)
        body = self._request('GET', key)
        if body is None:
            raise FileNotFoundError(django_name)
        return body

    def delete(self, django_name: str) -> None:
        key = self.object_key(django_name)
        try:
            self._request('DELETE', key)
        except BunnyStorageError as exc:
            if '404' in str(exc):
                return
            raise

    def exists(self, django_name: str) -> bool:
        key = self.object_key(django_name)
        req = urllib.request.Request(self._url(key), method='HEAD')
        req.add_header('AccessKey', self.access_key)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return 200 <= resp.status < 300
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return False
            raise BunnyStorageError(f'Bunny HTTP {exc.code}') from exc

    def list_prefix(self, subpath: str = '') -> list[str]:
        """Rekurzivní výpis pod prefixem (pro zálohy)."""
        rel = self._sanitize_rel(subpath)
        path = self.object_key(rel) if rel else self.root_prefix
        req = urllib.request.Request(f'{self._url(path)}?list=true', method='GET')
        req.add_header('AccessKey', self.access_key)
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                payload = json.loads(resp.read().decode('utf-8') or '[]')
        except urllib.error.HTTPError as exc:
            raise BunnyStorageError(f'Bunny list HTTP {exc.code}') from exc
        out: list[str] = []
        for item in payload if isinstance(payload, list) else []:
            name = item.get('ObjectName') or item.get('Name') or ''
            if not name:
                continue
            if item.get('IsDirectory'):
                out.extend(self.list_prefix(f'{rel}/{name}'.strip('/') if rel else name))
            else:
                out.append(f'{path}/{name}'.replace('//', '/'))
        return out


def get_bunny_client() -> BunnyStorageClient | None:
    if not getattr(settings, 'POSTAK_BUNNY_ENABLED', False):
        return None
    client = BunnyStorageClient(
        zone=settings.POSTAK_BUNNY_STORAGE_ZONE,
        access_key=settings.POSTAK_BUNNY_ACCESS_KEY,
        api_base=settings.POSTAK_BUNNY_API_BASE,
        root_prefix=settings.POSTAK_BUNNY_ROOT_PREFIX,
    )
    return client if client.enabled() else None
