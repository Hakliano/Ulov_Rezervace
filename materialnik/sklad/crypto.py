import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone as dt_timezone

from django.utils.dateparse import parse_datetime


def new_hmac_key():
    return secrets.token_hex(32)


def key_hash(secret):
    return hashlib.sha256(secret.encode('utf-8')).hexdigest()


def sign(secret, timestamp, event_id, body: bytes):
    msg = f'{timestamp}.{event_id}.'.encode('utf-8') + body
    return hmac.new(secret.encode('utf-8'), msg, hashlib.sha256).hexdigest()


def timestamp_ok(raw, max_age_seconds=300):
    if not raw:
        return False
    try:
        if raw.endswith('Z'):
            raw = raw[:-1] + '+00:00'
        dt = parse_datetime(raw)
        if dt is None:
            dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=dt_timezone.utc)
        now = datetime.now(dt_timezone.utc)
        return abs((now - dt.astimezone(dt_timezone.utc)).total_seconds()) <= max_age_seconds
    except (TypeError, ValueError):
        return False


def body_canonical(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
