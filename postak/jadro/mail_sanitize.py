"""Bezpečný HTML obsah e-mailu — bez skriptů a externích médií."""

from __future__ import annotations

import re
from html import escape
from html.parser import HTMLParser

BLOCK_TAGS = frozenset({'script', 'style', 'iframe', 'object', 'embed', 'form', 'link', 'meta', 'head', 'title'})


def prepare_email_html(raw: str) -> str:
    html = raw or ''
    body = re.search(r'(?is)<body[^>]*>(.*)</body>', html)
    if body:
        html = body.group(1)
    html = re.sub(r'(?is)<!DOCTYPE[^>]*>', '', html)
    html = re.sub(r'(?is)<head[^>]*>.*?</head>', '', html)
    html = re.sub(r'(?is)<style[^>]*>.*?</style>', '', html)
    html = re.sub(r'(?is)<script[^>]*>.*?</script>', '', html)
    return html.strip()


def html_looks_rendered(safe_html: str) -> bool:
    if not safe_html or len(safe_html) < 20:
        return False
    visible = re.sub(r'(?s)<[^>]+>', '', safe_html)
    visible = re.sub(r'\s+', ' ', visible).strip()
    if len(visible) < 12:
        return False
    if re.search(r'(?i)(@media|font-face|!important)\s*\{', safe_html):
        return False
    return True


class _Stripper(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in BLOCK_TAGS:
            self._skip += 1
            return
        if tag == 'img':
            self.out.append('<span class="img-blocked">[obrázek]</span>')
            return
        clean = []
        for key, val in attrs:
            key = key.lower()
            if key.startswith('on'):
                continue
            if tag == 'a' and key == 'href':
                href = (val or '').strip()
                if href.lower().startswith(('http://', 'https://', 'mailto:', 'tel:')):
                    clean.append((key, href))
                continue
            if key in ('src', 'srcset'):
                continue
            clean.append((key, val))
        self.out.append('<' + tag)
        for key, val in clean:
            if val is None:
                self.out.append(f' {key}')
            else:
                self.out.append(f' {key}="{escape(val, quote=True)}"')
        self.out.append('>')

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in BLOCK_TAGS:
            self._skip = max(0, self._skip - 1)
            return
        if tag == 'img':
            return
        if self._skip:
            return
        self.out.append(f'</{tag}>')

    def handle_data(self, data):
        if self._skip:
            return
        self.out.append(escape(data))

    def handle_entityref(self, name):
        if self._skip:
            return
        self.out.append(f'&{name};')

    def handle_charref(self, name):
        if self._skip:
            return
        self.out.append(f'&#{name};')


def sanitize_html(html: str) -> str:
    parser = _Stripper()
    parser.feed(html or '')
    parser.close()
    return ''.join(parser.out)


def html_to_plain(html: str) -> str:
    text = re.sub(r'(?is)<(script|style).*?>.*?</\1>', ' ', html or '')
    text = re.sub(r'(?i)<br\s*/?>', '\n', text)
    text = re.sub(r'(?i)</p\s*>', '\n\n', text)
    text = re.sub(r'(?i)</(li|div|blockquote|tr)\s*>', '\n', text)
    text = re.sub(r'(?s)<[^>]+>', ' ', text)
    text = re.sub(r'[ \t]+\n', '\n', text)
    return re.sub(r'\n{3,}', '\n\n', text).strip()


def looks_like_html(body: str) -> bool:
    return bool(re.search(r'<\s*(p|br|div|ul|ol|li|strong|em|b|i|u|a|blockquote|span)\b', body or '', re.I))


def normalize_compose_body(body: str) -> tuple[str, str]:
    raw = (body or '').strip()
    if looks_like_html(raw):
        safe = sanitize_html(raw)
    elif raw:
        parts = []
        for line in raw.split('\n'):
            parts.append(f'<p>{escape(line)}</p>' if line.strip() else '<p><br></p>')
        safe = sanitize_html(''.join(parts)) if parts else ''
    else:
        safe = ''
    plain = html_to_plain(safe) if safe else ''
    return safe, plain


def display_bodies(text: str, html_raw: str) -> tuple[str, str]:
    text = (text or '').strip()
    prepared = prepare_email_html(html_raw) if html_raw else ''
    safe = sanitize_html(prepared) if prepared else ''
    if safe and html_looks_rendered(safe):
        if not text:
            text = re.sub(r'(?s)<[^>]+>', ' ', safe)
            text = re.sub(r'\s+', ' ', text).strip()
        return text, safe
    if text:
        return text, ''
    if html_raw:
        plain = re.sub(r'(?is)<(script|style).*?>.*?</\1>', ' ', html_raw)
        plain = re.sub(r'(?s)<[^>]+>', ' ', plain)
        plain = re.sub(r'\s+', ' ', plain).strip()
        return plain, ''
    return '', ''
