"""Odeslání zprávy přes SMTP a uložení do Odeslané."""

from __future__ import annotations

import re
import smtplib
import ssl
import time
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate, make_msgid, parseaddr

import imaplib

from .mail_actions import sent_folder
from .mail_imap import MailError, imap_session, _cfg
from .mail_sanitize import html_to_plain, normalize_compose_body, sanitize_html
from .mail_secrets import decrypt_secret
from .models import EmailSchranka

TIMEOUT = 25
CTX = ssl.create_default_context()


def _addresses(raw: str):
    out = []
    for part in (raw or '').replace(';', ',').split(','):
        part = part.strip()
        if part:
            name, addr = parseaddr(part)
            out.append(formataddr((name, addr)) if name else addr)
    return out


def _podpis_jiz_v_tele(safe_body: str, podpis: str) -> bool:
    if not podpis:
        return False
    if 'posta-podpis' in (safe_body or ''):
        return True
    pod = re.sub(r'\s+', ' ', html_to_plain(podpis)).strip().lower()
    telo = re.sub(r'\s+', ' ', html_to_plain(safe_body or '')).strip().lower()
    return bool(pod and len(pod) > 8 and pod in telo)


def build_message(schranka: EmailSchranka, *, to, cc='', bcc='', subject, body, attachments=None, in_reply_to=''):
    attachments = attachments or []
    safe_body, text_body = normalize_compose_body(body)
    podpis = sanitize_html(schranka.podpis_html or '')
    html_body = f'<div class="posta-body">{safe_body}</div>'
    if podpis and not _podpis_jiz_v_tele(safe_body, podpis):
        html_body += f'<div class="posta-podpis">{podpis}</div>'
        text_body += '\n\n--\n' + html_to_plain(podpis)

    msg = MIMEMultipart('mixed')
    msg['From'] = schranka.email
    msg['To'] = ', '.join(_addresses(to))
    if cc:
        msg['Cc'] = ', '.join(_addresses(cc))
    msg['Subject'] = subject or ''
    msg['Date'] = formatdate(localtime=True)
    msg['Message-ID'] = make_msgid(domain=schranka.email.split('@')[-1])
    if in_reply_to:
        msg['In-Reply-To'] = in_reply_to
        msg['References'] = in_reply_to

    alt = MIMEMultipart('alternative')
    alt.attach(MIMEText(text_body, 'plain', 'utf-8'))
    alt.attach(MIMEText(html_body, 'html', 'utf-8'))
    msg.attach(alt)

    for name, data, ctype in attachments:
        main, sub = (ctype or 'application/octet-stream').split('/', 1) if '/' in (ctype or '') else ('application', 'octet-stream')
        part = MIMEBase(main, sub)
        part.set_payload(data)
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename="{name}"')
        msg.attach(part)

    recipients = _addresses(to) + _addresses(cc) + _addresses(bcc)
    return msg, recipients


def re_strip_html(html):
    import re
    text = re.sub(r'(?s)<[^>]+>', ' ', html or '')
    return re.sub(r'\s+', ' ', text).strip()


def send_message(schranka: EmailSchranka, *, to, cc='', bcc='', subject, body, attachments=None, in_reply_to=''):
    if not _addresses(to):
        raise MailError('Vyplňte příjemce.')
    msg, recipients = build_message(
        schranka,
        to=to,
        cc=cc,
        bcc=bcc,
        subject=subject,
        body=body,
        attachments=attachments,
        in_reply_to=in_reply_to,
    )
    raw = msg.as_bytes()
    cfg = _cfg(schranka)
    host = schranka.smtp_host
    port = int(schranka.smtp_port)
    try:
        if schranka.smtp_ssl:
            smtp = smtplib.SMTP_SSL(host, port, timeout=TIMEOUT, context=CTX)
        else:
            smtp = smtplib.SMTP(host, port, timeout=TIMEOUT)
            if schranka.smtp_starttls:
                smtp.starttls(context=CTX)
        smtp.login(cfg['user'], cfg['password'])
        smtp.sendmail(schranka.email, recipients, raw)
        smtp.quit()
    except smtplib.SMTPAuthenticationError as exc:
        raise MailError('SMTP autentizace selhala.') from exc
    except OSError as exc:
        raise MailError('Nelze se připojit k SMTP serveru.') from exc

    sent = sent_folder(schranka)
    try:
        with imap_session(schranka) as client:
            client.append(
                sent,
                '',
                imaplib.Time2Internaldate(time.time()),
                raw,
            )
    except Exception:
        pass
    return msg['Message-ID']


def send_system_message(schranka: EmailSchranka, *, to, subject, html_body, text_body):
    """Systémová zpráva — bez kopie do složky Odeslané (bez citlivých údajů v historii)."""
    if not _addresses(to):
        raise MailError('Vyplňte příjemce.')
    msg = MIMEMultipart('alternative')
    msg['From'] = schranka.email
    msg['To'] = ', '.join(_addresses(to))
    msg['Subject'] = subject or ''
    msg['Date'] = formatdate(localtime=True)
    msg['Message-ID'] = make_msgid(domain=schranka.email.split('@')[-1])
    msg.attach(MIMEText(text_body or '', 'plain', 'utf-8'))
    msg.attach(MIMEText(html_body or '', 'html', 'utf-8'))
    recipients = _addresses(to)
    raw = msg.as_bytes()
    cfg = _cfg(schranka)
    host = schranka.smtp_host
    port = int(schranka.smtp_port)
    try:
        if schranka.smtp_ssl:
            smtp = smtplib.SMTP_SSL(host, port, timeout=TIMEOUT, context=CTX)
        else:
            smtp = smtplib.SMTP(host, port, timeout=TIMEOUT)
            if schranka.smtp_starttls:
                smtp.starttls(context=CTX)
        smtp.login(cfg['user'], cfg['password'])
        smtp.sendmail(schranka.email, recipients, raw)
        smtp.quit()
    except smtplib.SMTPAuthenticationError as exc:
        raise MailError('SMTP autentizace selhala.') from exc
    except OSError as exc:
        raise MailError('Nelze se připojit k SMTP serveru.') from exc
    return msg['Message-ID']
