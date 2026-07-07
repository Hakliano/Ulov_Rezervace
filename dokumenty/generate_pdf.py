#!/usr/bin/env python3
"""Vygeneruje PDF z HTML dokumentů (Microsoft Edge headless)."""

import os
import subprocess
import sys
from pathlib import Path

from build_sales_html import main as build_sales_html

ROOT = Path(__file__).resolve().parent
PDF_DIR = ROOT / 'pdf'


def find_edge() -> str | None:
    candidates = [
        os.environ.get('PROGRAMFILES(X86)', r'C:\Program Files (x86)') + r'\Microsoft\Edge\Application\msedge.exe',
        os.environ.get('PROGRAMFILES', r'C:\Program Files') + r'\Microsoft\Edge\Application\msedge.exe',
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def html_to_pdf(edge: str, html_path: Path, pdf_path: Path) -> None:
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    url = html_path.resolve().as_uri()
    subprocess.run(
        [
            edge,
            '--headless',
            '--disable-gpu',
            '--no-pdf-header-footer',
            f'--print-to-pdf={pdf_path.resolve()}',
            url,
        ],
        check=True,
        capture_output=True,
    )


def main() -> int:
    edge = find_edge()
    if not edge:
        print('Microsoft Edge nenalezen — otevřete HTML v prohlížeči a použijte Tisk → Uložit jako PDF.', file=sys.stderr)
        return 1

    if build_sales_html() != 0:
        return 1

    docs = [
        (ROOT / 'prehled-pro-sales-a-marketing.html', PDF_DIR / 'PREHLED-pro-sales-a-marketing.pdf'),
        (ROOT / 'smlouva-o-zpracovani-osobnich-udaju.html', PDF_DIR / 'Smlouva-o-zpracovani-osobnich-udaju.pdf'),
        (ROOT / 'priloha-01-kategorie-osobnich-udaju.html', PDF_DIR / 'Priloha-01-kategorie-osobnich-udaju.pdf'),
        (ROOT / 'priloha-02-technicka-organizacni-opatreni.html', PDF_DIR / 'Priloha-02-technicka-organizacni-opatreni.pdf'),
        (ROOT / 'priloha-03-dalsi-zpracovatele.html', PDF_DIR / 'Priloha-03-dalsi-zpracovatele.pdf'),
        (ROOT / 'ropa-zaznamy-o-cinnostech-zpracovani.html', PDF_DIR / 'ROPA-zaznamy-o-cinnostech-zpracovani.pdf'),
    ]

    for html_path, pdf_path in docs:
        if not html_path.is_file():
            print(f'Chybí: {html_path}', file=sys.stderr)
            return 1
        print(f'Generuji {pdf_path.name}…')
        html_to_pdf(edge, html_path, pdf_path)
        print(f'  OK: {pdf_path}')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
