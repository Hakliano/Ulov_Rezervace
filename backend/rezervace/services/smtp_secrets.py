"""Šifrování SMTP hesel at rest (Fernet).

Hodnota v DB má prefix enc:v1:. Starý plaintext se při čtení bere jako heslo
a při dalším save() se zašifruje. Klíč: SMTP_ENCRYPTION_KEY, jinak SECRET_KEY.
"""

from __future__ import annotations

import base64
import hashlib
import logging

from django.conf import settings

logger = logging.getLogger(__name__)

SMTP_SECRET_PREFIX = 'enc:v1:'


def _fernet():
    from cryptography.fernet import Fernet

    raw = (getattr(settings, 'SMTP_ENCRYPTION_KEY', '') or '').strip()
    material = raw or f'smtp-at-rest|{settings.SECRET_KEY}'
    if len(raw) == 44:
        try:
            return Fernet(raw.encode())
        except ValueError:
            pass
    digest = hashlib.sha256(material.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def is_encrypted_smtp_secret(value: str | None) -> bool:
    return bool(value) and str(value).startswith(SMTP_SECRET_PREFIX)


def encrypt_smtp_secret(value: str | None) -> str:
    text = (value or '').strip()
    if not text:
        return ''
    if is_encrypted_smtp_secret(text):
        return text
    token = _fernet().encrypt(text.encode()).decode()
    return f'{SMTP_SECRET_PREFIX}{token}'


def decrypt_smtp_secret(value: str | None) -> str:
    text = (value or '').strip()
    if not text:
        return ''
    if not is_encrypted_smtp_secret(text):
        return text
    token = text[len(SMTP_SECRET_PREFIX):]
    try:
        return _fernet().decrypt(token.encode()).decode()
    except Exception:
        logger.warning('SMTP heslo v DB nejde dešifrovat — zkontrolujte SMTP_ENCRYPTION_KEY / SECRET_KEY.')
        return ''
