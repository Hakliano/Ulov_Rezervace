"""FLOW Mail — IMAP on-demand (bez ukládání schránky do DB)."""

from __future__ import annotations

import email
import imaplib
import re
from contextlib import contextmanager
from email.header import decode_header, make_header
from email.utils import parseaddr, parsedate_to_datetime

from rezervace.models import RezervacniNastaveni
from rezervace.services.emails import get_email_config, odeslat_volny_email

IMAP_TIMEOUT = 20
LIST_LIMIT_DEFAULT = 40
LIST_LIMIT_MAX = 80
BODY_MAX_CHARS = 50_000


class MailError(Exception):
    """Chyba připojení / schránky — bezpečná pro API detail."""


def get_imap_config(salon):
    try:
        nast = salon.rezervacni_nastaveni
    except RezervacniNastaveni.DoesNotExist:
        nast = None
    smtp = get_email_config(salon)
    host = ((nast.imap_host if nast else '') or '').strip() or 'imap.forpsi.com'
    port = int((nast.imap_port if nast else None) or 993)
    use_ssl = True if nast is None else bool(nast.imap_use_ssl)
    enabled = bool(nast and nast.imap_enabled)
    ready = bool(enabled and smtp['smtp_ready'] and host and smtp['user'] and smtp['password'])
    return {
        'host': host,
        'port': port,
        'use_ssl': use_ssl,
        'user': smtp['user'],
        'password': smtp['password'],
        'enabled': enabled,
        'ready': ready,
        'mailbox': smtp['user'] or '',
    }


def _decode_header_value(raw):
    if raw is None:
        return ''
    try:
        return str(make_header(decode_header(raw)))
    except Exception:
        if isinstance(raw, bytes):
            return raw.decode('utf-8', errors='replace')
        return str(raw)


def _decode_payload(part):
    payload = part.get_payload(decode=True)
    if payload is None:
        data = part.get_payload()
        return data if isinstance(data, str) else ''
    charset = part.get_content_charset() or 'utf-8'
    try:
        return payload.decode(charset, errors='replace')
    except LookupError:
        return payload.decode('utf-8', errors='replace')


def _html_to_text(html):
    text = re.sub(r'(?is)<(script|style).*?>.*?</\1>', ' ', html)
    text = re.sub(r'(?i)<br\s*/?>', '\n', text)
    text = re.sub(r'(?i)</p>', '\n\n', text)
    text = re.sub(r'(?i)</div>', '\n', text)
    text = re.sub(r'(?s)<[^>]+>', ' ', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'[ \t]+\n', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def extract_body(msg):
    """Preferuje text/plain; HTML jen jako fallback (převedeno na text)."""
    plain_parts = []
    html_parts = []
    if msg.is_multipart():
        for part in msg.walk():
            ctype = (part.get_content_type() or '').lower()
            disp = (part.get('Content-Disposition') or '').lower()
            if 'attachment' in disp:
                continue
            if ctype == 'text/plain':
                plain_parts.append(_decode_payload(part))
            elif ctype == 'text/html':
                html_parts.append(_decode_payload(part))
    else:
        ctype = (msg.get_content_type() or '').lower()
        body = _decode_payload(msg)
        if ctype == 'text/html':
            html_parts.append(body)
        else:
            plain_parts.append(body)
    text = '\n\n'.join(p.strip() for p in plain_parts if p and p.strip())
    if not text and html_parts:
        text = _html_to_text('\n'.join(html_parts))
    if len(text) > BODY_MAX_CHARS:
        text = text[:BODY_MAX_CHARS] + '\n\n… (zkráceno)'
    return text


def _msg_date_iso(msg):
    raw = msg.get('Date')
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            from datetime import timezone as dt_tz

            dt = dt.replace(tzinfo=dt_tz.utc)
        return dt.isoformat()
    except Exception:
        return None


def _summary_from_bytes(raw_bytes, uid, flags=b''):
    msg = email.message_from_bytes(raw_bytes)
    from_name, from_email = parseaddr(_decode_header_value(msg.get('From')))
    subject = _decode_header_value(msg.get('Subject')) or '(bez předmětu)'
    unseen = b'\\Seen' not in flags
    return {
        'uid': int(uid),
        'from_name': from_name or '',
        'from_email': from_email or '',
        'subject': subject,
        'date': _msg_date_iso(msg),
        'unseen': unseen,
        'message_id': (msg.get('Message-ID') or '').strip(),
    }


@contextmanager
def _imap_connection(cfg):
    if not cfg['ready']:
        raise MailError('Schránka ve FLOW není zapnutá. Majitelka ji nastaví v administraci webu (E-mail).')
    try:
        if cfg['use_ssl']:
            client = imaplib.IMAP4_SSL(cfg['host'], cfg['port'], timeout=IMAP_TIMEOUT)
        else:
            client = imaplib.IMAP4(cfg['host'], cfg['port'], timeout=IMAP_TIMEOUT)
        client.login(cfg['user'], cfg['password'])
    except imaplib.IMAP4.error as exc:
        raise MailError('Přihlášení k IMAP selhalo. Zkontrolujte heslo a IMAP server.') from exc
    except OSError as exc:
        raise MailError(f'Nelze se připojit k IMAP ({cfg["host"]}).') from exc
    try:
        yield client
    finally:
        try:
            client.logout()
        except Exception:
            pass


def list_messages(salon, limit=LIST_LIMIT_DEFAULT, offset=0):
    cfg = get_imap_config(salon)
    limit = max(1, min(int(limit or LIST_LIMIT_DEFAULT), LIST_LIMIT_MAX))
    offset = max(0, int(offset or 0))
    with _imap_connection(cfg) as client:
        typ, _ = client.select('INBOX', readonly=True)
        if typ != 'OK':
            raise MailError('Nelze otevřít INBOX.')
        typ, data = client.uid('search', None, 'ALL')
        if typ != 'OK':
            raise MailError('Nelze načíst seznam zpráv.')
        uids = data[0].split() if data and data[0] else []
        uids = list(reversed(uids))  # nejnovější první
        total = len(uids)
        page = uids[offset: offset + limit]
        items = []
        for uid in page:
            typ, fetched = client.uid(
                'fetch',
                uid,
                '(FLAGS BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE MESSAGE-ID)])',
            )
            if typ != 'OK' or not fetched or not fetched[0]:
                continue
            meta = fetched[0]
            if not isinstance(meta, tuple) or len(meta) < 2:
                continue
            header_bytes = meta[1]
            flags_match = re.search(rb'FLAGS \(([^)]*)\)', meta[0] if isinstance(meta[0], bytes) else b'')
            flags = flags_match.group(1) if flags_match else b''
            items.append(_summary_from_bytes(header_bytes, uid, flags))
        return {
            'ready': True,
            'mailbox': cfg['mailbox'],
            'total': total,
            'limit': limit,
            'offset': offset,
            'items': items,
        }


def get_message(salon, uid, mark_seen=True):
    cfg = get_imap_config(salon)
    uid = int(uid)
    with _imap_connection(cfg) as client:
        typ, _ = client.select('INBOX', readonly=not mark_seen)
        if typ != 'OK':
            raise MailError('Nelze otevřít INBOX.')
        peek = 'BODY.PEEK[]' if not mark_seen else 'BODY[]'
        typ, fetched = client.uid('fetch', str(uid), f'(FLAGS {peek})')
        if typ != 'OK' or not fetched or not fetched[0]:
            raise MailError('Zpráva nenalezena.')
        meta = fetched[0]
        if not isinstance(meta, tuple) or len(meta) < 2:
            raise MailError('Zpráva nenalezena.')
        flags_match = re.search(rb'FLAGS \(([^)]*)\)', meta[0] if isinstance(meta[0], bytes) else b'')
        flags = flags_match.group(1) if flags_match else b''
        msg = email.message_from_bytes(meta[1])
        summary = _summary_from_bytes(meta[1], uid, flags)
        summary['body'] = extract_body(msg)
        summary['to'] = _decode_header_value(msg.get('To'))
        summary['in_reply_to'] = (msg.get('In-Reply-To') or '').strip()
        summary['references'] = (msg.get('References') or '').strip()
        if mark_seen:
            summary['unseen'] = False
        return summary


def send_mail_message(salon, *, to, subject, body, reply_uid=None):
    cfg = get_imap_config(salon)
    smtp = get_email_config(salon)
    if not smtp['smtp_ready']:
        raise MailError('SMTP není nastavené — nelze odeslat e-mail.')
    to = (to or '').strip()
    subject = (subject or '').strip()
    body = (body or '').strip()
    if not to or '@' not in to:
        raise MailError('Zadejte platnou adresu příjemce.')
    if not subject:
        raise MailError('Zadejte předmět.')
    if not body:
        raise MailError('Zadejte text zprávy.')

    headers = {}
    if reply_uid:
        detail = get_message(salon, reply_uid, mark_seen=False)
        mid = detail.get('message_id') or ''
        if mid:
            headers['In-Reply-To'] = mid
            refs = (detail.get('references') or '').strip()
            headers['References'] = f'{refs} {mid}'.strip() if refs else mid
        if not subject.lower().startswith('re:'):
            subject = f'Re: {subject}'

    ok = odeslat_volny_email(salon, to, subject, body, headers=headers or None)
    if not ok:
        raise MailError('Odeslání selhalo.')
    return {
        'ok': True,
        'to': to,
        'subject': subject,
        'mailbox': cfg['mailbox'],
    }
