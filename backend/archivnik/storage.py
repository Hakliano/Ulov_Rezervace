"""Úložiště souborů Archivníku. Bunny s odděleným prefixem; bez CDN v testech."""

from __future__ import annotations

import mimetypes
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings

from salons.bunny import BunnyUploadError, is_bunny_configured
from salons.image_optimize import ImageOptimizeError, optimize_image_bytes

MAX_BYTES = 20 * 1024 * 1024
IMAGE_TYPES = frozenset({'image/jpeg', 'image/png', 'image/webp', 'image/gif'})
DOCUMENT_TYPES = frozenset({'application/pdf', 'image/jpeg', 'image/png', 'image/webp'})
ALLOWED_TYPES = IMAGE_TYPES | DOCUMENT_TYPES | frozenset({'application/octet-stream'})

_LOCAL: dict[str, tuple[bytes, str]] = {}


def _storage_host():
    region = settings.BUNNY_STORAGE_REGION
    if region:
        return f'https://{region}.storage.bunnycdn.com'
    return 'https://storage.bunnycdn.com'


def tenant_uuid(salon) -> str:
    partner = getattr(salon, 'partner_nastaveni', None)
    if partner and getattr(partner, 'tenant_uuid', None):
        return str(partner.tenant_uuid)
    return f'salon-{salon.id}'


def guess_kind(content_type: str, requested: str | None = None) -> str:
    if requested in ('fotografie', 'dokument'):
        return requested
    return 'fotografie' if content_type in IMAGE_TYPES else 'dokument'


def prepare_upload(raw: bytes, content_type: str, filename: str = '', druh: str = 'dokument'):
    if len(raw) > MAX_BYTES:
        raise BunnyUploadError('Soubor je větší než 20 MB.')
    ctype = (content_type or '').split(';')[0].strip().lower() or 'application/octet-stream'
    if ctype == 'application/octet-stream':
        guessed, _ = mimetypes.guess_type(filename or '')
        ctype = (guessed or ctype).lower()
    if druh == 'fotografie' and ctype not in IMAGE_TYPES:
        raise BunnyUploadError('Fotografie: JPG, PNG, WebP nebo GIF.')
    if druh == 'dokument' and ctype not in DOCUMENT_TYPES:
        raise BunnyUploadError('Dokument: PDF, JPG nebo PNG.')
    if ctype not in ALLOWED_TYPES:
        raise BunnyUploadError('Nepodporovaný typ souboru.')
    if ctype in IMAGE_TYPES:
        try:
            data, ctype, ext = optimize_image_bytes(raw, ctype)
        except ImageOptimizeError as exc:
            raise BunnyUploadError(str(exc)) from exc
    else:
        data = raw
        ext = 'pdf' if ctype == 'application/pdf' else (mimetypes.guess_extension(ctype) or '.bin').lstrip('.')
        if ext == 'jpe':
            ext = 'jpg'
    return data, ctype, ext


def put_bytes(storage_key: str, data: bytes, content_type: str) -> None:
    if not is_bunny_configured():
        _LOCAL[storage_key] = (data, content_type)
        return
    storage_url = f'{_storage_host()}/{settings.BUNNY_STORAGE_ZONE}/{storage_key}'
    req = Request(storage_url, data=data, method='PUT')
    req.add_header('AccessKey', settings.BUNNY_STORAGE_API_KEY)
    req.add_header('Content-Type', content_type)
    try:
        with urlopen(req, timeout=45) as resp:
            if resp.status not in (200, 201):
                raise BunnyUploadError(f'Bunny.net vrátilo stav {resp.status}')
    except HTTPError as e:
        raise BunnyUploadError(f'Nahrání selhalo: HTTP {e.code}') from e
    except URLError as e:
        raise BunnyUploadError(f'Chyba připojení k Bunny.net: {e.reason}') from e


def get_bytes(storage_key: str) -> tuple[bytes, str]:
    if storage_key in _LOCAL:
        return _LOCAL[storage_key]
    if not is_bunny_configured():
        raise BunnyUploadError('Soubor není k dispozici.')
    storage_url = f'{_storage_host()}/{settings.BUNNY_STORAGE_ZONE}/{storage_key}'
    req = Request(storage_url, method='GET')
    req.add_header('AccessKey', settings.BUNNY_STORAGE_API_KEY)
    try:
        with urlopen(req, timeout=30) as resp:
            ctype = resp.headers.get('Content-Type') or 'application/octet-stream'
            return resp.read(), ctype
    except HTTPError as e:
        raise BunnyUploadError(f'Stáhnutí selhalo: HTTP {e.code}') from e
    except URLError as e:
        raise BunnyUploadError(f'Chyba připojení k Bunny.net: {e.reason}') from e


def store_file(salon, raw: bytes, content_type: str, filename: str, druh: str, asset_uuid=None) -> tuple[str, str, str, int]:
    asset_uuid = asset_uuid or uuid.uuid4()
    data, ctype, ext = prepare_upload(raw, content_type, filename, druh)
    key = f'archivnik/{tenant_uuid(salon)}/{asset_uuid}.{ext}'
    put_bytes(key, data, ctype)
    return str(asset_uuid), key, ctype, len(data)


def stored_file_exists(storage_key: str) -> bool:
    if not storage_key:
        return False
    if storage_key in _LOCAL:
        return True
    if not is_bunny_configured():
        return False
    try:
        get_bytes(storage_key)
        return True
    except BunnyUploadError:
        return False


def delete_stored_file(storage_key: str) -> None:
    """Smaže jeden soubor. HTTP 404 = už neexistuje (OK). Jiná chyba se nesmí spolknout."""
    if not storage_key:
        return
    if not is_bunny_configured():
        _LOCAL.pop(storage_key, None)
        return
    storage_url = f'{_storage_host()}/{settings.BUNNY_STORAGE_ZONE}/{storage_key}'
    req = Request(storage_url, method='DELETE')
    req.add_header('AccessKey', settings.BUNNY_STORAGE_API_KEY)
    try:
        with urlopen(req, timeout=30) as resp:
            if resp.status not in (200, 202, 204):
                raise BunnyUploadError(f'Bunny.net DELETE vrátilo stav {resp.status}')
    except HTTPError as e:
        if e.code == 404:
            _LOCAL.pop(storage_key, None)
            return
        raise BunnyUploadError(f'Odstranění souboru selhalo: HTTP {e.code}') from e
    except URLError as e:
        raise BunnyUploadError(f'Chyba připojení k Bunny.net při mazání: {e.reason}') from e
    _LOCAL.pop(storage_key, None)


def delete_bytes(storage_key: str) -> None:
    """Tiché mazání pro jednotlivý Asset v UI. Kompletní výmaz kartotéky používá delete_stored_file."""
    if not storage_key:
        return
    _LOCAL.pop(storage_key, None)
    if not is_bunny_configured():
        return
    storage_url = f'{_storage_host()}/{settings.BUNNY_STORAGE_ZONE}/{storage_key}'
    req = Request(storage_url, method='DELETE')
    req.add_header('AccessKey', settings.BUNNY_STORAGE_API_KEY)
    try:
        urlopen(req, timeout=15)
    except (HTTPError, URLError):
        pass
