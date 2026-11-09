"""Test IMAP/SMTP — jen přihlášení, bez odeslání ani změny schránky."""

from __future__ import annotations

import imaplib
import smtplib
import ssl
from dataclasses import dataclass

TIMEOUT = 20
CTX = ssl.create_default_context()


@dataclass
class Vysledek:
    ok: bool
    detail: str


def test_imap(*, host, port, use_ssl, user, password):
    host = (host or '').strip()
    user = (user or '').strip()
    if not host or not user or not password:
        return Vysledek(False, 'Chybí server, uživatel nebo heslo.')
    try:
        if use_ssl:
            client = imaplib.IMAP4_SSL(host, int(port), timeout=TIMEOUT, ssl_context=CTX)
        else:
            client = imaplib.IMAP4(host, int(port), timeout=TIMEOUT)
            client.starttls(ssl_context=CTX)
        client.login(user, password)
        client.logout()
        return Vysledek(True, 'IMAP přihlášení OK.')
    except imaplib.IMAP4.error:
        return Vysledek(False, 'IMAP: přihlášení selhalo.')
    except OSError as exc:
        return Vysledek(False, f'IMAP: nelze se připojit ({exc.__class__.__name__}).')
    except Exception:
        return Vysledek(False, 'IMAP: neočekávaná chyba.')


def test_smtp(*, host, port, use_ssl, starttls, user, password):
    host = (host or '').strip()
    user = (user or '').strip()
    if not host or not user or not password:
        return Vysledek(False, 'Chybí server, uživatel nebo heslo.')
    client = None
    try:
        if use_ssl:
            client = smtplib.SMTP_SSL(host, int(port), timeout=TIMEOUT, context=CTX)
        else:
            client = smtplib.SMTP(host, int(port), timeout=TIMEOUT)
            if starttls:
                client.starttls(context=CTX)
        client.login(user, password)
        client.quit()
        return Vysledek(True, 'SMTP přihlášení OK.')
    except smtplib.SMTPAuthenticationError:
        return Vysledek(False, 'SMTP: autentizace selhala.')
    except OSError as exc:
        return Vysledek(False, f'SMTP: nelze se připojit ({exc.__class__.__name__}).')
    except Exception:
        return Vysledek(False, 'SMTP: neočekávaná chyba.')
    finally:
        if client:
            try:
                client.close()
            except Exception:
                pass
