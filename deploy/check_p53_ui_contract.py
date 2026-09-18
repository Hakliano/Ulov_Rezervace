#!/usr/bin/env python3
"""P5.3 UI contract against FLOW/Archivník static files.

Django API image contains only backend/, so these checks must run on the host
against either the git tree or the deployed nginx tree (www-staging).

Usage:
  python3 deploy/check_p53_ui_contract.py
  python3 deploy/check_p53_ui_contract.py --root /opt/ulov/www-staging
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _read(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(f'chybí {path}')
    return path.read_text(encoding='utf-8')


def check(root: Path) -> list[str]:
    errors: list[str] = []
    flow = root / 'flow'
    archivnik = root / 'archivnik'

    def fail(msg: str) -> None:
        errors.append(msg)

    try:
        js = _read(flow / 'customer-card.js')
        html = _read(flow / 'index.html')
        app_js = _read(flow / 'app.js')
        arch_js = _read(archivnik / 'app.js')
    except FileNotFoundError as exc:
        return [str(exc)]

    for needle in (
        '/flow/kartoteka/',
        'archivnik_customer_uuid',
        'Založit zákazníka',
        'Otevřít kartu zákazníka',
        'Otevřít kompletní kartu v Archivníku',
        'data-kt-nova-rez',
    ):
        if needle not in js:
            fail(f'flow/customer-card.js musí obsahovat {needle!r}')

    for banned in (
        '/flow/zakaznicke-karty',
        'zakaznicke-karty/',
        'customer_card_id',
        'ceka_na_potvrzeni',
        'Odeslat potvrzení',
        'Aktivovat lokálně',
    ):
        if banned in js:
            fail(f'flow/customer-card.js nesmí obsahovat {banned!r}')

    if 'ceka_na_potvrzeni' in html:
        fail("flow/index.html nesmí obsahovat 'ceka_na_potvrzeni'")

    if 'api-staging.ulovklienty.cz' not in app_js:
        fail("flow/app.js musí obsahovat staging API host")

    if "interniParts.join('\\n')" in app_js or 'interniParts.join("\\n")' in app_js:
        fail('flow/app.js nesmí skládat nova-interni přes newline')
    if "interniParts.join(' · ')" not in app_js:
        fail("flow/app.js musí skládat telefon a poznámku přes ' · '")

    for needle in (
        "get('zakaznik')",
        'openDeepLinkCustomer',
        'pendingCustomerUuid',
        'await openCustomer(uuid)',
    ):
        if needle not in arch_js:
            fail(f'archivnik/app.js musí obsahovat {needle!r}')

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description='P5.3 FLOW/Archivník UI contract')
    parser.add_argument(
        '--root',
        default='',
        help='Kořen se složkami flow/ a archivnik/ (default: kořen gitu)',
    )
    args = parser.parse_args()
    if args.root:
        root = Path(args.root).resolve()
    else:
        root = Path(__file__).resolve().parent.parent
    errors = check(root)
    if errors:
        print(f'FAIL  P5.3 UI contract ({root})')
        for item in errors:
            print(f'  - {item}')
        return 1
    print(f'OK    P5.3 UI contract ({root})')
    return 0


if __name__ == '__main__':
    sys.exit(main())
