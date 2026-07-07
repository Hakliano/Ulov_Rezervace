#!/usr/bin/env python3
"""Vygeneruje pouze PDF sales dokumentu z Markdown."""

import sys
from pathlib import Path

from build_sales_html import main as build_sales_html
from generate_pdf import PDF_DIR, find_edge, html_to_pdf

ROOT = Path(__file__).resolve().parent


def main() -> int:
    if build_sales_html() != 0:
        return 1

    edge = find_edge()
    if not edge:
        print('Microsoft Edge nenalezen — otevřete dokumenty/prehled-pro-sales-a-marketing.html a Ctrl+P → PDF.')
        return 1

    html_path = ROOT / 'prehled-pro-sales-a-marketing.html'
    pdf_path = PDF_DIR / 'PREHLED-pro-sales-a-marketing.pdf'
    print(f'Generuji {pdf_path.name}…')
    html_to_pdf(edge, html_path, pdf_path)
    print(f'Hotovo: {pdf_path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
