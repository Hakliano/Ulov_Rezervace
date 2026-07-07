"""Změna velikosti a komprese obrázků před nahráním na CDN."""

from io import BytesIO

from django.conf import settings
from PIL import Image, ImageOps


class ImageOptimizeError(Exception):
    pass

ALLOWED_CONTENT_TYPES = frozenset({
    'image/jpeg', 'image/png', 'image/webp', 'image/gif',
})

_EXT_BY_TYPE = {
    'image/jpeg': 'jpg',
    'image/png': 'png',
    'image/webp': 'webp',
    'image/gif': 'gif',
}


def _max_px() -> int:
    return int(getattr(settings, 'IMAGE_UPLOAD_MAX_PX', 1920))


def _jpeg_quality() -> int:
    return int(getattr(settings, 'IMAGE_UPLOAD_JPEG_QUALITY', 85))


def _webp_quality() -> int:
    return int(getattr(settings, 'IMAGE_UPLOAD_WEBP_QUALITY', 85))


def _resize_if_needed(img: Image.Image, max_px: int) -> Image.Image:
    w, h = img.size
    if max(w, h) <= max_px:
        return img
    resized = img.copy()
    resized.thumbnail((max_px, max_px), Image.Resampling.LANCZOS)
    return resized


def _save_jpeg(img: Image.Image) -> bytes:
    if img.mode in ('RGBA', 'LA', 'P'):
        bg = Image.new('RGB', img.size, (255, 255, 255))
        if img.mode == 'P':
            img = img.convert('RGBA')
        bg.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
        img = bg
    elif img.mode != 'RGB':
        img = img.convert('RGB')
    buf = BytesIO()
    img.save(buf, format='JPEG', quality=_jpeg_quality(), optimize=True)
    return buf.getvalue()


def _save_png(img: Image.Image) -> bytes:
    if img.mode == 'P':
        img = img.convert('RGBA')
    buf = BytesIO()
    img.save(buf, format='PNG', optimize=True)
    return buf.getvalue()


def _save_webp(img: Image.Image) -> bytes:
    buf = BytesIO()
    img.save(buf, format='WEBP', quality=_webp_quality(), method=4)
    return buf.getvalue()


def _save_gif(img: Image.Image) -> bytes:
    buf = BytesIO()
    img.save(buf, format='GIF', optimize=True)
    return buf.getvalue()


def optimize_image_bytes(data: bytes, content_type: str) -> tuple[bytes, str, str]:
    """
    Zmenší obrázek na max IMAGE_UPLOAD_MAX_PX (delší strana) a zkomprimuje.
    Vrací (bytes, content_type, přípona).
    Animované GIFy se nemění.
    """
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise ImageOptimizeError('Povolené formáty: JPG, PNG, WebP, GIF.')

    max_px = _max_px()
    if max_px <= 0:
        ext = _EXT_BY_TYPE.get(content_type, 'jpg')
        return data, content_type, ext

    try:
        with Image.open(BytesIO(data)) as img:
            if content_type == 'image/gif' and getattr(img, 'n_frames', 1) > 1:
                return data, content_type, 'gif'

            img = ImageOps.exif_transpose(img)
            img = _resize_if_needed(img, max_px)

            if content_type == 'image/jpeg':
                return _save_jpeg(img), 'image/jpeg', 'jpg'
            if content_type == 'image/png':
                return _save_png(img), 'image/png', 'png'
            if content_type == 'image/webp':
                return _save_webp(img), 'image/webp', 'webp'
            if content_type == 'image/gif':
                return _save_gif(img), 'image/gif', 'gif'
    except ImageOptimizeError:
        raise
    except Exception as exc:
        raise ImageOptimizeError('Soubor není platný obrázek nebo se nepodařilo zpracovat.') from exc

    raise ImageOptimizeError('Nepodporovaný formát obrázku.')
