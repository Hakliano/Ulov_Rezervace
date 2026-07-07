import mimetypes
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings

from .image_optimize import ALLOWED_CONTENT_TYPES, ImageOptimizeError, optimize_image_bytes


class BunnyUploadError(Exception):
    pass


def _storage_host():
    region = settings.BUNNY_STORAGE_REGION
    if region:
        return f'https://{region}.storage.bunnycdn.com'
    return 'https://storage.bunnycdn.com'


def is_bunny_configured():
    return bool(
        settings.BUNNY_STORAGE_ZONE
        and settings.BUNNY_STORAGE_API_KEY
        and settings.BUNNY_CDN_BASE_URL
    )


def upload_image(file_obj, salon_id, folder='galerie'):
    if not is_bunny_configured():
        raise BunnyUploadError(
            'Bunny.net není nakonfigurován. Vyplňte proměnné v backend/.env'
        )

    content_type = getattr(file_obj, 'content_type', '') or 'application/octet-stream'
    if content_type not in ALLOWED_CONTENT_TYPES:
        ext = mimetypes.guess_extension(content_type) or ''
        if ext not in {'.jpg', '.jpeg', '.png', '.webp', '.gif'}:
            raise BunnyUploadError('Povolené formáty: JPG, PNG, WebP, GIF.')

    raw = file_obj.read()
    try:
        data, content_type, ext = optimize_image_bytes(raw, content_type)
    except ImageOptimizeError as exc:
        raise BunnyUploadError(str(exc)) from exc

    prefix = settings.BUNNY_STORAGE_PATH_PREFIX.strip('/')
    filename = f'{uuid.uuid4().hex}.{ext}'
    remote_path = f'{prefix}/salon-{salon_id}/{folder}/{filename}'

    storage_url = f'{_storage_host()}/{settings.BUNNY_STORAGE_ZONE}/{remote_path}'

    req = Request(storage_url, data=data, method='PUT')
    req.add_header('AccessKey', settings.BUNNY_STORAGE_API_KEY)
    req.add_header('Content-Type', content_type)

    try:
        with urlopen(req, timeout=30) as resp:
            if resp.status not in (200, 201):
                raise BunnyUploadError(f'Bunny.net vrátilo stav {resp.status}')
    except HTTPError as e:
        raise BunnyUploadError(f'Nahrání selhalo: HTTP {e.code}') from e
    except URLError as e:
        raise BunnyUploadError(f'Chyba připojení k Bunny.net: {e.reason}') from e

    cdn_base = settings.BUNNY_CDN_BASE_URL.rstrip('/')
    return f'{cdn_base}/{remote_path}'


def delete_image(remote_url):
    if not is_bunny_configured() or not remote_url:
        return

    cdn_base = settings.BUNNY_CDN_BASE_URL.rstrip('/')
    if not remote_url.startswith(cdn_base):
        return

    remote_path = remote_url[len(cdn_base):].lstrip('/')
    storage_url = f'{_storage_host()}/{settings.BUNNY_STORAGE_ZONE}/{remote_path}'

    req = Request(storage_url, method='DELETE')
    req.add_header('AccessKey', settings.BUNNY_STORAGE_API_KEY)

    try:
        urlopen(req, timeout=15)
    except (HTTPError, URLError):
        pass
