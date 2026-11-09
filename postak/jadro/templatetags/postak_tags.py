from django import template
from django.conf import settings
from django.urls import reverse

from jadro.models import Profil

register = template.Library()


@register.simple_tag
def postak_static(name):
    prefix = (settings.POSTAK_PREFIX or '').rstrip('/')
    return f'{prefix}/static/{name.lstrip("/")}'


@register.simple_tag
def postak_logo():
    return getattr(
        settings,
        'POSTAK_LOGO_URL',
        'https://haklweb.b-cdn.net/modernik/Cheerful%20Pigeon%20Mail%20Carrier%20Logo.webp',
    )


@register.filter
def user_initials(user):
    if not user or not user.is_authenticated:
        return '?'
    name = (user.get_full_name() or user.get_username() or '').strip()
    if not name:
        return '?'
    parts = name.split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    return name[:2].upper()


@register.filter
def get_item(mapping, key):
    if mapping is None:
        return []
    return mapping.get(key, [])


@register.filter
def profil_foto(user):
    try:
        foto = user.profil.foto
    except Profil.DoesNotExist:
        return ''
    if not foto:
        return ''
    return reverse('profil_foto', args=[user.pk])
