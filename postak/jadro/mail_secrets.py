"""Šifrování hesel schránek — Fernet, prefix enc:v1:."""

from __future__ import annotations

import logging

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)

PREFIX = 'enc:v1:'


class MailDecryptError(Exception):
    pass


def _fernet():
    from cryptography.fernet import Fernet

    raw = (getattr(settings, 'POSTAK_MAIL_ENCRYPTION_KEY', '') or '').strip()
    if not raw:
        raise ImproperlyConfigured('POSTAK_MAIL_ENCRYPTION_KEY is not set.')
    try:
        return Fernet(raw.encode('ascii'))
    except Exception as exc:
        raise ImproperlyConfigured('POSTAK_MAIL_ENCRYPTION_KEY is invalid.') from exc


def encrypt_secret(value: str | None) -> str:
    text = (value or '').strip()
    if not text:
        return ''
    if text.startswith(PREFIX):
        return text
    token = _fernet().encrypt(text.encode('utf-8')).decode('ascii')
    return f'{PREFIX}{token}'


def decrypt_secret(value: str | None) -> str:
    text = (value or '').strip()
    if not text:
        return ''
    if not text.startswith(PREFIX):
        return ''
    try:
        return _fernet().decrypt(text[len(PREFIX):].encode('ascii')).decode('utf-8')
    except Exception as exc:
        raise MailDecryptError('Credential cannot be decrypted.') from exc
