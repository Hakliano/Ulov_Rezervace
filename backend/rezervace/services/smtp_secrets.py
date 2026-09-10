"""SMTP hesla at rest: Fernet (AES-128-CBC + HMAC-SHA256), prefix enc:v1:.

Klíč je jen SMTP_ENCRYPTION_KEY (+ volitelně SMTP_ENCRYPTION_PREVIOUS_KEYS).
Žádný fallback na SECRET_KEY. Hodnota bez enc:v1: se jako heslo nepoužije.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)

SMTP_SECRET_PREFIX = 'enc:v1:'


class SmtpDecryptError(Exception):
    """Ciphertext existuje, ale nejde dešifrovat aktuálním ani previous klíčem."""


def _key_list():
    primary = (getattr(settings, 'SMTP_ENCRYPTION_KEY', '') or '').strip()
    if not primary:
        raise ImproperlyConfigured('SMTP_ENCRYPTION_KEY is not set.')
    keys = [primary]
    previous = getattr(settings, 'SMTP_ENCRYPTION_PREVIOUS_KEYS', None) or []
    if isinstance(previous, str):
        previous = [part.strip() for part in previous.split(',') if part.strip()]
    keys.extend(previous)
    return keys


def _multi_fernet():
    from cryptography.fernet import Fernet, MultiFernet, InvalidToken  # noqa: F401

    fernets = []
    for raw in _key_list():
        try:
            fernets.append(Fernet(raw.encode('ascii')))
        except Exception:
            logger.error('SMTP encryption key entry is invalid and was skipped.')
    if not fernets:
        raise ImproperlyConfigured('No valid SMTP_ENCRYPTION_KEY.')
    if len(fernets) == 1:
        return fernets[0]
    return MultiFernet(fernets)


def is_encrypted_smtp_secret(value: str | None) -> bool:
    return bool(value) and str(value).startswith(SMTP_SECRET_PREFIX)


def encrypt_smtp_secret(value: str | None) -> str:
    text = (value or '').strip()
    if not text:
        return ''
    if is_encrypted_smtp_secret(text):
        return text
    token = _multi_fernet().encrypt(text.encode('utf-8')).decode('ascii')
    return f'{SMTP_SECRET_PREFIX}{token}'


def decrypt_smtp_secret(value: str | None) -> str:
    """Vrátí plaintext, nebo '' když heslo není nastavené.

    Vyvolá SmtpDecryptError, když je enc:v1: nečitelný.
    Hodnotu bez prefixu nepoužije (fail closed).
    """
    text = (value or '').strip()
    if not text:
        return ''
    if not is_encrypted_smtp_secret(text):
        return ''
    token = text[len(SMTP_SECRET_PREFIX):]
    try:
        return _multi_fernet().decrypt(token.encode('ascii')).decode('utf-8')
    except Exception as exc:
        raise SmtpDecryptError('SMTP credential cannot be decrypted.') from exc
