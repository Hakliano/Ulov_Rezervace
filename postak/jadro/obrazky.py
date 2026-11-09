from django.core.files.base import ContentFile

from .models import Profil

MAX_FOTO_BYTES = 2 * 1024 * 1024
PRIPONY = {'jpg': 'image/jpeg', 'png': 'image/png', 'webp': 'image/webp'}


def pripona_obrazku(data):
    """Skutečný obsah, ne přípona ani Content-Type od prohlížeče."""
    if not data:
        return ''
    if data.startswith(b'\xff\xd8\xff'):
        return 'jpg'
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'png'
    if len(data) >= 12 and data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return 'webp'
    return ''


def _profil(user):
    try:
        return user.profil
    except Profil.DoesNotExist:
        return None


def smaz_foto(user):
    profil = _profil(user)
    if profil and profil.foto:
        profil.foto.delete(save=True)


def uloz_foto(user, pripona, data):
    smaz_foto(user)
    profil, _ = Profil.objects.get_or_create(user=user)
    profil.foto.save(f'{user.pk}.{pripona}', ContentFile(data), save=True)
    return profil
