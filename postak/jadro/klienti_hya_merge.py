"""Sloučení a diff polí HYA ↔ cache Pošťáku."""

from __future__ import annotations

from django.utils.dateparse import parse_datetime

from jadro.klienti_models import KlientHya
from jadro.obchodni_stavy import (
    OBCHODNI_STAV_LABELS,
    kanon_do_hya_api,
    kanon_z_api_stavu,
)

_SKIP_EMPTY_OVERWRITE = frozenset({
    'telefon', 'web', 'lokalita', 'zdroj', 'poznamka', 'kontakt_jmeno',
})
_ALWAYS_APPLY = frozenset({'jmeno', 'email', 'stav', 'stav_label', 'ma_web', 'ma_rezervace'})


def _norm_str(v) -> str:
    return (v or '').strip()


def _tri_from_api(val) -> str:
    if val is True:
        return 'yes'
    if val is False:
        return 'no'
    return 'unknown'


def defaults_from_hya_api(client: dict) -> dict:
    stav = kanon_z_api_stavu(client.get('status') or '')[:32]
    upr = parse_datetime(client.get('updated_on') or '')
    return {
        'jmeno': (client.get('company_name') or '')[:200],
        'kontakt_jmeno': (client.get('contact_name') or '')[:200],
        'email': (client.get('email') or '')[:254],
        'telefon': (client.get('phone') or '')[:200],
        'web': (client.get('web') or '')[:400],
        'lokalita': (client.get('location') or '')[:200],
        'zdroj': (client.get('source') or '')[:120],
        'ma_web': _tri_from_api(client.get('has_website'))[:12],
        'ma_rezervace': _tri_from_api(client.get('has_booking_system'))[:12],
        'poznamka': (client.get('note') or client.get('description') or ''),
        'stav': stav,
        'stav_label': (OBCHODNI_STAV_LABELS.get(stav) or '')[:80],
        'remote_upraveno': upr,
    }


def merge_hya_api_into_defaults(existing: KlientHya, incoming: dict) -> dict:
    out = dict(incoming)
    for field in _SKIP_EMPTY_OVERWRITE:
        if field not in out:
            continue
        local_val = getattr(existing, field, None)
        api_val = out[field]
        if _norm_str(local_val) and not _norm_str(api_val):
            out[field] = local_val
    for field in _ALWAYS_APPLY:
        if field in incoming:
            out[field] = incoming[field]
    if incoming.get('remote_upraveno'):
        out['remote_upraveno'] = incoming['remote_upraveno']
    return out


def _tri_to_api(cache_val: str):
    v = (cache_val or '').strip().lower()
    if v == 'yes':
        return True
    if v == 'no':
        return False
    return None


def hya_patch_z_formulare(lokal: KlientHya, post) -> tuple[dict, dict]:
    patch: dict = {}
    expected: dict = {}

    def track(api_key, new_val, old_val, *, clear_null=False):
        if new_val is None:
            return
        old_s = _norm_str(old_val)
        new_s = _norm_str(new_val) if isinstance(new_val, str) else new_val
        if isinstance(new_val, str) and old_s == new_s:
            return
        if clear_null and isinstance(new_val, str) and new_s == '' and old_s:
            patch[api_key] = None
        else:
            patch[api_key] = new_val if not isinstance(new_val, str) else new_s
        expected[api_key] = old_val

    def post_val(key):
        return (post.get(key), key in post)

    if 'jmeno' in post:
        track('company_name', _norm_str(post.get('jmeno')), lokal.jmeno)
    if 'kontakt_jmeno' in post:
        track('contact_name', _norm_str(post.get('kontakt_jmeno')), lokal.kontakt_jmeno, clear_null=True)
    if 'email' in post:
        track('email', _norm_str(post.get('email')).lower(), lokal.email)
    if 'telefon' in post:
        track('phone', _norm_str(post.get('telefon')), lokal.telefon, clear_null=True)
    if 'web' in post:
        track('web', _norm_str(post.get('web')), lokal.web, clear_null=True)
    if 'lokalita' in post:
        track('location', _norm_str(post.get('lokalita')), lokal.lokalita, clear_null=True)
    if 'zdroj' in post:
        track('source', _norm_str(post.get('zdroj')), lokal.zdroj, clear_null=True)
    if 'poznamka' in post:
        track('note', _norm_str(post.get('poznamka')), lokal.poznamka, clear_null=True)
    if 'ma_web' in post:
        raw = (post.get('ma_web') or '').strip()
        nv = _tri_to_api(raw) if raw else None
        ov = _tri_to_api(lokal.ma_web)
        if nv != ov:
            patch['has_website'] = nv
            expected['has_website'] = ov
    if 'ma_rezervace' in post:
        raw = (post.get('ma_rezervace') or '').strip()
        nv = _tri_to_api(raw) if raw else None
        ov = _tri_to_api(lokal.ma_rezervace)
        if nv != ov:
            patch['has_booking_system'] = nv
            expected['has_booking_system'] = ov
    if 'stav' in post:
        stav = kanon_z_api_stavu(_norm_str(post.get('stav')))
        if stav and stav != lokal.stav:
            patch['status'] = kanon_do_hya_api(stav)
            expected['status'] = kanon_do_hya_api(lokal.stav)

    return patch, expected