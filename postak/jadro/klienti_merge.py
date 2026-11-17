"""Sloučení a diff polí Moderník ↔ cache Pošťáku."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.utils.dateparse import parse_datetime

from .klienti_models import KlientModernik

# Pole, u kterých prázdná hodnota z API nepřepíše neprázdnou cache (sync směrem z Moderníku).
_SKIP_EMPTY_OVERWRITE = frozenset({
    'telefon', 'web', 'adresa', 'mesto', 'cast_obce', 'ico', 'poznamka',
})

_ALWAYS_APPLY = frozenset({'jmeno', 'email', 'stav', 'stav_label', 'sektor_remote_id', 'sektor_nazev'})


def _norm_str(v) -> str:
    return (v or '').strip()


def _gps_z_api(val):
    if val in (None, ''):
        return None
    try:
        dec = Decimal(str(val).replace(',', '.'))
    except (InvalidOperation, ValueError):
        return None
    return dec


def defaults_from_api_item(item: dict) -> dict:
    lat = _gps_z_api(item.get('latitude'))
    lon = _gps_z_api(item.get('longitude'))
    if lat == 0 and lon == 0:
        lat, lon = None, None
    upr = parse_datetime(item.get('upraveno') or '') 
    return {
        'jmeno': (item.get('jmeno') or '')[:200],
        'email': (item.get('email') or '')[:254],
        'telefon': (item.get('telefon') or '')[:200],
        'web': (item.get('web') or '')[:400],
        'adresa': item.get('adresa') or '',
        'mesto': (item.get('mesto') or '')[:120],
        'cast_obce': (item.get('cast_obce') or '')[:120],
        'latitude': lat,
        'longitude': lon,
        'ico': (item.get('ico') or '')[:20],
        'poznamka': item.get('poznamka') or '',
        'stav': (item.get('stav') or '')[:32],
        'stav_label': (item.get('stav_label') or '')[:80],
        'sektor_remote_id': item.get('sektor_id'),
        'sektor_nazev': (item.get('sektor_nazev') or '')[:80],
        'remote_upraveno': upr,
    }


def merge_api_into_defaults(existing: KlientModernik, incoming: dict) -> dict:
    """Spojí API hodnoty s existující cache — neprázdná cache + prázdné API → zachovat cache."""
    out = dict(incoming)
    for field in _SKIP_EMPTY_OVERWRITE:
        if field not in out:
            continue
        api_val = out[field]
        local_val = getattr(existing, field, None)
        if field in ('latitude', 'longitude'):
            if api_val is None and local_val is not None:
                out[field] = local_val
            continue
        if _norm_str(local_val) and not _norm_str(api_val):
            out[field] = local_val
    # Vždy autoritativní z API
    for field in _ALWAYS_APPLY:
        if field in incoming:
            out[field] = incoming[field]
    if incoming.get('remote_upraveno'):
        out['remote_upraveno'] = incoming['remote_upraveno']
    return out


def _post_val(post, key: str):
    if key not in post:
        return None
    return (post.get(key) or '').strip()


def _post_decimal(post, key: str):
    raw = _post_val(post, key)
    if not raw:
        return None
    return _gps_z_api(raw)


def modernik_patch_z_formulare(lokal: KlientModernik, post) -> tuple[dict, dict]:
    """Vrátí (patch pro API, expected_fields). Null v patch = úmyslné vymazání pole."""
    patch: dict = {}
    expected: dict = {}

    def track(field, new_val, old_val, *, clear_null=False):
        if field == 'sektor_id':
            old_n = old_val
            new_n = int(new_val) if new_val not in (None, '', 'None') else None
            if old_n != new_n:
                patch['sektor_id'] = new_n
                expected['sektor_id'] = old_n
            return
        old_s = _norm_str(old_val)
        new_s = _norm_str(new_val)
        if old_s == new_s:
            return
        if clear_null and new_s == '' and old_s:
            patch[field] = None
        else:
            patch[field] = new_s if new_s or field in ('jmeno', 'email') else ''
        expected[field] = old_val if field not in ('latitude', 'longitude') else (
            str(old_val) if old_val is not None else ''
        )

    def track_post(field, post_key, old_val, *, clear_null=False, lower=False):
        raw = _post_val(post, post_key)
        if raw is None:
            return
        if lower:
            raw = raw.lower()
        track(field, raw, old_val, clear_null=clear_null)

    track_post('jmeno', 'jmeno', lokal.jmeno)
    track_post('email', 'email', lokal.email, lower=True)
    track_post('telefon', 'telefon', lokal.telefon, clear_null=True)
    track_post('web', 'web', lokal.web, clear_null=True)
    track_post('adresa', 'adresa', lokal.adresa, clear_null=True)
    track_post('mesto', 'mesto', lokal.mesto, clear_null=True)
    track_post('cast_obce', 'cast_obce', lokal.cast_obce, clear_null=True)
    track_post('ico', 'ico', lokal.ico, clear_null=True)
    track_post('poznamka', 'poznamka', lokal.poznamka, clear_null=True)

    lat_new = _post_decimal(post, 'latitude') if 'latitude' in post else None
    lon_new = _post_decimal(post, 'longitude') if 'longitude' in post else None
    if lat_new is not None or lon_new is not None:
        lat_new = lat_new if lat_new is not None else lokal.latitude
        lon_new = lon_new if lon_new is not None else lokal.longitude
    if lat_new != lokal.latitude or lon_new != lokal.longitude:
        patch['latitude'] = '' if lat_new is None else str(lat_new)
        patch['longitude'] = '' if lon_new is None else str(lon_new)
        expected['latitude'] = '' if lokal.latitude is None else str(lokal.latitude)
        expected['longitude'] = '' if lokal.longitude is None else str(lokal.longitude)

    stav_new = _post_val(post, 'stav')
    if stav_new is not None and stav_new and stav_new != lokal.stav:
        patch['stav'] = stav_new
        expected['stav'] = lokal.stav

    if 'sektor_id' in post:
        track('sektor_id', post.get('sektor_id'), lokal.sektor_remote_id)

    return patch, expected