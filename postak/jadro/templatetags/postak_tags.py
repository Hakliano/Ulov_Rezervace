from django import template
from django.conf import settings

register = template.Library()


@register.simple_tag
def postak_static(name):
    prefix = (settings.POSTAK_PREFIX or '').rstrip('/')
    return f'{prefix}/static/{name.lstrip("/")}'
