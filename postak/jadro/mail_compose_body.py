"""Citace a úvodní tělo pro psaní zpráv."""

from __future__ import annotations

from html import escape


def _lines_to_html(text: str) -> str:
    return escape(text or '').replace('\r\n', '\n').replace('\n', '<br>')


def quote_reply_html(*, author: str, body_text: str) -> str:
    return (
        '<p><br></p>'
        f'<blockquote class="posta-quote">'
        f'<p><strong>{escape(author)}</strong> napsal(a):</p>'
        f'<p>{_lines_to_html(body_text)}</p>'
        '</blockquote>'
    )


def quote_forward_html(*, from_: str, to: str, subject: str, body_text: str) -> str:
    return (
        '<p><br></p>'
        '<blockquote class="posta-quote">'
        '<p><strong>Přeposlaná zpráva</strong></p>'
        f'<p>Od: {escape(from_)}<br>'
        f'Komu: {escape(to)}<br>'
        f'Předmět: {escape(subject)}</p>'
        f'<p>{_lines_to_html(body_text)}</p>'
        '</blockquote>'
    )
