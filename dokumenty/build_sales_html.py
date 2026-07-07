#!/usr/bin/env python3
"""Vygeneruje HTML pro sales dokument z PREHLED_PRO_SALES_A_MARKETING.md."""

import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
MD_PATH = PROJECT / 'PREHLED_PRO_SALES_A_MARKETING.md'
OUT_HTML = ROOT / 'prehled-pro-sales-a-marketing.html'


def inline(text: str) -> str:
    text = html.escape(text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    text = re.sub(
        r'\[([^\]]+)\]\(([^)]+)\)',
        r'<a href="\2">\1</a>',
        text,
    )
    return text


def is_table_row(line: str) -> bool:
    s = line.strip()
    return s.startswith('|') and s.endswith('|') and '|' in s[1:-1]


def is_separator_row(line: str) -> bool:
    return bool(re.match(r'^\|[\s\-:|]+\|$', line.strip()))


def parse_table(lines: list[str], start: int) -> tuple[str, int]:
    rows = []
    i = start
    while i < len(lines) and is_table_row(lines[i]):
        if not is_separator_row(lines[i]):
            cells = [c.strip() for c in lines[i].strip().strip('|').split('|')]
            rows.append(cells)
        i += 1
    if not rows:
        return '', start

    thead = ''
    tbody_rows = []
    for idx, row in enumerate(rows):
        tag = 'th' if idx == 0 else 'td'
        cells = ''.join(f'<{tag}>{inline(c)}</{tag}>' for c in row)
        if idx == 0:
            thead = f'<thead><tr>{cells}</tr></thead>'
        else:
            tbody_rows.append(f'<tr>{cells}</tr>')
    table = f'<table class="data-table">{thead}<tbody>{"".join(tbody_rows)}</tbody></table>'
    return table, i


def md_to_html(md: str) -> str:
    lines = md.replace('\r\n', '\n').split('\n')
    parts: list[str] = []
    i = 0
    in_ul = False
    in_ol = False

    def close_lists():
        nonlocal in_ul, in_ol
        if in_ul:
            parts.append('</ul>')
            in_ul = False
        if in_ol:
            parts.append('</ol>')
            in_ol = False

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            close_lists()
            i += 1
            continue

        if stripped == '---':
            close_lists()
            parts.append('<hr class="section-break">')
            i += 1
            continue

        if is_table_row(stripped):
            close_lists()
            table, i = parse_table(lines, i)
            parts.append(table)
            continue

        if stripped.startswith('### '):
            close_lists()
            parts.append(f'<h3>{inline(stripped[4:])}</h3>')
            i += 1
            continue

        if stripped.startswith('## '):
            close_lists()
            parts.append(f'<h2>{inline(stripped[3:])}</h2>')
            i += 1
            continue

        if stripped.startswith('# '):
            close_lists()
            parts.append(f'<h1 class="doc-title-main">{inline(stripped[2:])}</h1>')
            i += 1
            continue

        if re.match(r'^\d+\.\s', stripped):
            if in_ul:
                parts.append('</ul>')
                in_ul = False
            if not in_ol:
                parts.append('<ol>')
                in_ol = True
            item = re.sub(r'^\d+\.\s+', '', stripped)
            parts.append(f'<li>{inline(item)}</li>')
            i += 1
            continue

        if stripped.startswith('- '):
            if in_ol:
                parts.append('</ol>')
                in_ol = False
            if not in_ul:
                parts.append('<ul>')
                in_ul = True
            parts.append(f'<li>{inline(stripped[2:])}</li>')
            i += 1
            continue

        if stripped.startswith('*') and stripped.endswith('*') and not stripped.startswith('**'):
            close_lists()
            parts.append(f'<p class="footer-note">{inline(stripped.strip("*"))}</p>')
            i += 1
            continue

        close_lists()
        parts.append(f'<p>{inline(stripped)}</p>')
        i += 1

    close_lists()
    return '\n'.join(parts)


def wrap_body(content: str) -> str:
    return f'''<!DOCTYPE html>
<html lang="cs">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ULOV KLIENTY — přehled pro sales a marketing</title>
  <link rel="stylesheet" href="styles/legal.css">
  <link rel="stylesheet" href="styles/sales.css">
</head>
<body class="has-print-bar">
  <div class="print-bar no-print">
    <span>ULOV KLIENTY — Přehled pro sales a marketing (náhled / PDF)</span>
    <button type="button" onclick="window.print()">Uložit jako PDF / Tisk</button>
  </div>

  <header class="doc-header sales-header">
    <p class="doc-brand">ULOV KLIENTY · Ulov Rezervaci</p>
    <h1 class="doc-title">Přehled pro sales a marketing</h1>
    <p class="doc-subtitle">Web salonu na míru · rezervace · administrace · e-maily · recenze</p>
    <dl class="doc-meta">
      <div><dt>Verze</dt><dd>červen 2026</dd></div>
      <div><dt>Web</dt><dd>www.ulovklienty.cz</dd></div>
      <div><dt>Interní</dt><dd>sales &amp; marketing</dd></div>
    </dl>
  </header>

  <article class="article">
{content}
  </article>

  <p class="footer-note">© ULOV KLIENTY — interní materiál pro obchod a marketing. Zdroj: PREHLED_PRO_SALES_A_MARKETING.md</p>
</body>
</html>
'''


def main() -> int:
    if not MD_PATH.is_file():
        print(f'Chybí: {MD_PATH}', file=sys.stderr)
        return 1

    md = MD_PATH.read_text(encoding='utf-8')
    # Přeskočit první nadpis v MD — je v hlavičce HTML
    md_body = re.sub(r'^# .+\n+', '', md, count=1)
    content = md_to_html(md_body)
    OUT_HTML.write_text(wrap_body(content), encoding='utf-8')
    print(f'OK: {OUT_HTML}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
