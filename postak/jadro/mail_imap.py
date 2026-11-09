"""IMAP čtení — stránkování podle UID, bez stažení celé schránky."""

from __future__ import annotations

import email
import imaplib
import re
import ssl
from contextlib import contextmanager
from email.header import decode_header, make_header
from email.utils import parseaddr, parsedate_to_datetime

from .mail_sanitize import display_bodies
from .mail_secrets import MailDecryptError, decrypt_secret
from .models import EmailSchranka

TIMEOUT = 25
CTX = ssl.create_default_context()
STRANKA_VELIKOST = 25
BODY_MAX = 200_000


class MailError(Exception):
    pass


def _cfg(schranka: EmailSchranka):
    heslo = decrypt_secret(schranka.heslo_sifra)
    if not heslo:
        raise MailError('Schránka nemá uložené heslo.')
    return {
        'host': schranka.imap_host,
        'port': schranka.imap_port,
        'use_ssl': schranka.imap_ssl,
        'user': (schranka.prihlasovaci_jmeno or schranka.email).strip(),
        'password': heslo,
    }


def _decode_header(raw):
    if raw is None:
        return ''
    try:
        return str(make_header(decode_header(raw)))
    except Exception:
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
    text = re.sub(r'(?s)<[^>]+>', ' ', text)
    return re.sub(r'\n{3,}', '\n\n', text).strip()


def _safe_folder(name: str) -> str:
    name = (name or 'INBOX').strip()
    if not name or '\x00' in name or len(name) > 200:
        raise MailError('Neplatná složka.')
    return name


@contextmanager
def imap_session(schranka: EmailSchranka, *, timeout=None):
    cfg = _cfg(schranka)
    socket_timeout = TIMEOUT if timeout is None else timeout
    try:
        if cfg['use_ssl']:
            client = imaplib.IMAP4_SSL(cfg['host'], int(cfg['port']), timeout=socket_timeout, ssl_context=CTX)
        else:
            client = imaplib.IMAP4(cfg['host'], int(cfg['port']), timeout=socket_timeout)
            client.starttls(ssl_context=CTX)
        client.login(cfg['user'], cfg['password'])
    except MailDecryptError as exc:
        raise MailError('Heslo schránky nejde načíst.') from exc
    except imaplib.IMAP4.error as exc:
        raise MailError('Přihlášení k IMAP selhalo.') from exc
    except OSError as exc:
        raise MailError('Nelze se připojit k IMAP serveru.') from exc
    try:
        yield client
    finally:
        try:
            client.logout()
        except Exception:
            pass


def _folder_uidvalidity(client, folder):
    typ, data = client.select(folder, readonly=True)
    if typ != 'OK':
        raise MailError('Složku nelze otevřít.')
    typ, resp = client.response('UIDVALIDITY')
    val = resp[0] if resp else None
    if isinstance(val, bytes):
        val = val.decode()
    return str(val or '')


def refresh_folder(schranka: EmailSchranka, *, folder='INBOX'):
    """IMAP NOOP + znovu SELECT — obnoví metadata složky bez stažení těl zpráv."""
    folder = _safe_folder(folder)
    with imap_session(schranka) as client:
        uidvalidity = _folder_uidvalidity(client, folder)
        typ, _ = client.noop()
        if typ != 'OK':
            raise MailError('Synchronizace se nezdařila.')
        return {'folder': folder, 'uidvalidity': uidvalidity}


def list_folders(schranka: EmailSchranka):
    with imap_session(schranka) as client:
        typ, data = client.list()
        if typ != 'OK' or not data:
            return [{'name': 'INBOX', 'label': 'Doručená'}]
        out = []
        seen = set()
        for row in data:
            if not row:
                continue
            line = row.decode() if isinstance(row, bytes) else str(row)
            m = re.search(r'\)\s+"([^"]*)"\s+"?([^"]+)"?$', line) or re.search(r'\)\s+(\S+)\s+(.+)$', line)
            if not m:
                continue
            name = m.group(2).strip('"')
            if not name or name in seen:
                continue
            seen.add(name)
            label = name
            low = name.lower()
            if low == 'inbox':
                label = 'Doručená'
            elif 'sent' in low or 'odesl' in low:
                label = 'Odeslané'
            elif 'draft' in low or 'koncept' in low:
                label = 'Koncepty'
            elif 'trash' in low or 'kos' in low or 'deleted' in low:
                label = 'Koš'
            out.append({'name': name, 'label': label})
        if 'INBOX' not in seen:
            out.insert(0, {'name': 'INBOX', 'label': 'Doručená'})
        return out


def list_page(schranka: EmailSchranka, *, folder='INBOX', page=1, per_page=STRANKA_VELIKOST):
    folder = _safe_folder(folder)
    page = max(1, int(page or 1))
    per_page = max(1, min(int(per_page or STRANKA_VELIKOST), 50))
    with imap_session(schranka) as client:
        uidvalidity = _folder_uidvalidity(client, folder)
        typ, data = client.uid('search', None, 'ALL')
        if typ != 'OK':
            raise MailError('Seznam zpráv nelze načíst.')
        uids = data[0].split() if data and data[0] else []
        uids = list(reversed(uids))
        total = len(uids)
        pages = max(1, (total + per_page - 1) // per_page)
        page = min(page, pages)
        offset = (page - 1) * per_page
        chunk = uids[offset: offset + per_page]
        items = []
        for uid in chunk:
            typ, fetched = client.uid(
                'fetch',
                uid,
                '(FLAGS BODY.PEEK[HEADER.FIELDS (FROM TO SUBJECT DATE MESSAGE-ID)])',
            )
            if typ != 'OK' or not fetched or not isinstance(fetched[0], tuple):
                continue
            raw_head = fetched[0][0]
            head = fetched[0][1]
            flags = b''
            if isinstance(raw_head, bytes):
                fm = re.search(rb'FLAGS \(([^)]*)\)', raw_head)
                flags = fm.group(1) if fm else b''
            msg = email.message_from_bytes(head)
            from_name, from_email = parseaddr(_decode_header(msg.get('From')))
            items.append({
                'uid': int(uid),
                'from_name': from_name or '',
                'from_email': from_email or '',
                'to': _decode_header(msg.get('To')),
                'subject': _decode_header(msg.get('Subject')) or '(bez předmětu)',
                'date': _format_date(msg),
                'unread': b'\\Seen' not in flags,
            })
        return {
            'folder': folder,
            'uidvalidity': uidvalidity,
            'items': items,
            'total': total,
            'page': page,
            'pages': pages,
            'per_page': per_page,
        }


def _format_date(msg):
    raw = msg.get('Date')
    if not raw:
        return ''
    try:
        return parsedate_to_datetime(raw).strftime('%d.%m.%Y %H:%M')
    except Exception:
        return _decode_header(raw)


def get_detail(schranka: EmailSchranka, *, folder, uid, mark_seen=True, uidvalidity=''):
    folder = _safe_folder(folder)
    uid = int(uid)
    with imap_session(schranka) as client:
        current = _folder_uidvalidity(client, folder)
        if uidvalidity and uidvalidity != current:
            raise MailError('Seznam zpráv se změnil. Obnovte stránku.')
        client.select(folder, readonly=not mark_seen)
        peek = 'BODY.PEEK[]' if not mark_seen else 'BODY[]'
        typ, fetched = client.uid('fetch', str(uid), f'(FLAGS {peek})')
        if typ != 'OK' or not fetched or not isinstance(fetched[0], tuple):
            raise MailError('Zpráva nenalezena.')
        raw_flags = fetched[0][0]
        body = fetched[0][1]
        flags = b''
        if isinstance(raw_flags, bytes):
            fm = re.search(rb'FLAGS \(([^)]*)\)', raw_flags)
            flags = fm.group(1) if fm else b''
        msg = email.message_from_bytes(body)
        text, html_raw = _extract_bodies(msg)
        body_text, body_html = display_bodies(text, html_raw)
        if mark_seen and b'\\Seen' not in flags:
            client.uid('store', str(uid), '+FLAGS', r'(\Seen)')
        return {
            'uid': uid,
            'uidvalidity': current,
            'folder': folder,
            'subject': _decode_header(msg.get('Subject')) or '(bez předmětu)',
            'from': _decode_header(msg.get('From')) or '',
            'to': _decode_header(msg.get('To')),
            'date': _format_date(msg),
            'unread': (not mark_seen) and (b'\\Seen' not in flags),
            'body_text': body_text,
            'body_html': body_html,
            'message_id': (msg.get('Message-ID') or '').strip(),
            'cc': _decode_header(msg.get('Cc')),
            'reply_to': _decode_header(msg.get('Reply-To') or msg.get('From')),
            'attachments': _attachments(msg),
        }


def _extract_bodies(msg):
    plain, html = [], []
    if msg.is_multipart():
        for part in msg.walk():
            ctype = (part.get_content_type() or '').lower()
            disp = (part.get('Content-Disposition') or '').lower()
            if 'attachment' in disp:
                continue
            if ctype == 'text/plain':
                plain.append(_decode_payload(part))
            elif ctype == 'text/html':
                html.append(_decode_payload(part))
    else:
        ctype = (msg.get_content_type() or '').lower()
        body = _decode_payload(msg)
        (html if ctype == 'text/html' else plain).append(body)
    text = '\n\n'.join(x.strip() for x in plain if x and x.strip())
    html_raw = '\n'.join(x for x in html if x)
    if not text and html_raw:
        text = _html_to_text(html_raw)
    if len(text) > BODY_MAX:
        text = text[:BODY_MAX] + '\n\n…'
    if len(html_raw) > BODY_MAX:
        html_raw = html_raw[:BODY_MAX] + '<p>…</p>'
    return text, html_raw


def _attachments(msg):
    out = []
    idx = 0
    for part in msg.walk():
        disp = (part.get('Content-Disposition') or '').lower()
        filename = part.get_filename()
        if 'attachment' not in disp and not filename:
            continue
        if filename:
            filename = _decode_header(filename)
        idx += 1
        payload = part.get_payload(decode=True) or b''
        out.append({
            'part': idx,
            'filename': filename or f'priloha-{idx}',
            'content_type': part.get_content_type() or 'application/octet-stream',
            'size': len(payload),
        })
    return out


def fetch_attachment(schranka: EmailSchranka, *, folder, uid, part_no, uidvalidity=''):
    folder = _safe_folder(folder)
    uid = int(uid)
    part_no = int(part_no)
    with imap_session(schranka) as client:
        current = _folder_uidvalidity(client, folder)
        if uidvalidity and uidvalidity != current:
            raise MailError('Seznam zpráv se změnil.')
        typ, fetched = client.uid('fetch', str(uid), '(BODY.PEEK[])')
        if typ != 'OK' or not fetched or not isinstance(fetched[0], tuple):
            raise MailError('Zpráva nenalezena.')
        msg = email.message_from_bytes(fetched[0][1])
        idx = 0
        for part in msg.walk():
            disp = (part.get('Content-Disposition') or '').lower()
            filename = part.get_filename()
            if 'attachment' not in disp and not filename:
                continue
            idx += 1
            if idx != part_no:
                continue
            data = part.get_payload(decode=True) or b''
            name = _decode_header(filename) if filename else f'priloha-{idx}'
            return data, name, part.get_content_type() or 'application/octet-stream'
    raise MailError('Příloha nenalezena.')


def overview_unseen(schranka: EmailSchranka, *, folder='INBOX', limit=8, timeout=8):
    """Lehký přehled nepřečtených — jen hlavičky, krátký timeout."""
    folder = _safe_folder(folder)
    limit = max(1, min(int(limit or 8), 20))
    with imap_session(schranka, timeout=timeout) as client:
        client.select(folder, readonly=True)
        typ, data = client.uid('search', None, 'UNSEEN')
        if typ != 'OK':
            raise MailError('Nepřečtené nelze načíst.')
        uids = data[0].split() if data and data[0] else []
        uids = sorted((int(x) for x in uids), reverse=True)
        total = len(uids)
        chunk = uids[:limit]
        items = []
        for uid in chunk:
            typ, fetched = client.uid(
                'fetch',
                str(uid),
                '(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])',
            )
            if typ != 'OK' or not fetched or not isinstance(fetched[0], tuple):
                continue
            msg = email.message_from_bytes(fetched[0][1])
            from_name, from_email = parseaddr(_decode_header(msg.get('From')))
            items.append({
                'uid': uid,
                'from_name': from_name or from_email or '',
                'from_email': from_email or '',
                'subject': _decode_header(msg.get('Subject')) or '(bez předmětu)',
                'date': _format_date(msg),
                'folder': folder,
            })
        return {'count': total, 'items': items}
