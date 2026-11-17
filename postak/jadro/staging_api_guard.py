"""Zabrání STAGING Pošťáku v zápisu proti LIVE CRM API."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

# Produkční hosty bez „staging“ v hostname.
_LIVE_MODERNIK_HOSTS = frozenset({
    'api.ulovklienty.cz',
    'www.ulovklienty.cz',
})
_LIVE_HYA_HOSTS = frozenset({
    'hereyouare.cz',
    'www.hereyouare.cz',
})

_WRITE_METHODS = frozenset({'POST', 'PATCH', 'PUT', 'DELETE'})


def _host(url: str) -> str:
    try:
        return (urlparse(url).hostname or '').lower().strip('.')
    except Exception:
        return ''


def _is_live_modernik_base(base: str) -> bool:
    h = _host(base)
    if not h:
        return False
    if 'staging' in h:
        return False
    return h in _LIVE_MODERNIK_HOSTS or h == 'api.ulovklienty.cz'


def _is_live_hya_base(base: str) -> bool:
    h = _host(base)
    if not h:
        return False
    if 'staging' in h:
        return False
    if h in _LIVE_HYA_HOSTS:
        return True
    return h.endswith('.hereyouare.cz') and not h.startswith('staging.')


def assert_staging_crm_targets() -> None:
    """Při STAGING režimu zakáže LIVE API base URL."""
    if not getattr(settings, 'POSTAK_STAGING_MODE', False):
        return
    problems = []
    mod = getattr(settings, 'MODERNIK_API_BASE', '') or ''
    hya = getattr(settings, 'HYA_API_BASE', '') or ''
    if mod and _is_live_modernik_base(mod):
        problems.append(f'MODERNIK_API_BASE ukazuje na LIVE: {mod}')
    if hya and _is_live_hya_base(hya):
        problems.append(f'HYA_API_BASE ukazuje na LIVE: {hya}')
    if problems:
        raise ImproperlyConfigured('; '.join(problems))


def block_live_crm_write(method: str, base_url: str, *, kind: str) -> None:
    """Volat před odchozím CRM HTTP zápisem (jen STAGING režim)."""
    if method.upper() not in _WRITE_METHODS:
        return
    if not getattr(settings, 'POSTAK_STAGING_MODE', False):
        return
    base = (base_url or '').strip()
    if kind == 'modernik' and _is_live_modernik_base(base):
        raise ImproperlyConfigured(
            f'STAGING: zápis na LIVE Moderník API je blokován ({base}).'
        )
    if kind == 'hya' and _is_live_hya_base(base):
        raise ImproperlyConfigured(
            f'STAGING: zápis na LIVE HYA API je blokován ({base}).'
        )