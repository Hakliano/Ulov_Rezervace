#!/usr/bin/env python3
"""P5.6A UI contract: delete + contact banner, no partner export/marketing tools."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

BANNER = '🔒 Kontaktní údaje jsou pro péči o zákazníka'
BANNER_BODY = (
    'E-mail a telefon používejte pouze v souvislosti s poskytovanou službou. '
    'Archivník není určen pro marketingové rozesílky ani tvorbu marketingových databází. '
    'Za způsob použití údajů odpovídá provozovna jako jejich správce.'
)


def _read(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(f'chybí {path}')
    return path.read_text(encoding='utf-8')


def check(root: Path) -> list[str]:
    errors: list[str] = []
    arch_js = root / 'archivnik' / 'app.js'
    arch_html = root / 'archivnik' / 'index.html'
    flow_js = root / 'flow' / 'customer-card.js'
    flow_html = root / 'flow' / 'index.html'

    try:
        app = _read(arch_js)
        html = _read(arch_html)
        cjs = _read(flow_js)
        fhtml = _read(flow_html)
    except FileNotFoundError as exc:
        return [str(exc)]

    def fail(msg: str) -> None:
        errors.append(msg)

    if BANNER not in app:
        fail('archivnik/app.js musí obsahovat kontaktní banner')
    if BANNER_BODY not in app:
        fail('archivnik/app.js musí obsahovat přesný text banneru')
    if 'Odstranit zákazníka a jeho data' not in app:
        fail('archivnik/app.js musí obsahovat akci výmazu')
    if 'je_spravce' not in app:
        fail('archivnik/app.js musí skrývat výmaz za je_spravce')
    if "method: 'DELETE'" not in app and 'method: "DELETE"' not in app:
        fail('archivnik/app.js musí volat DELETE zákazníka')
    if 'export_archivnik' in app or 'Exportovat všechny' in app:
        fail('archivnik/app.js nesmí obsahovat partner export')
    if 'newsletter' in app.lower():
        fail('archivnik/app.js nesmí obsahovat newsletter')
    if BANNER not in cjs:
        fail('flow/customer-card.js musí obsahovat kontaktní banner')
    if BANNER not in fhtml:
        fail('flow/index.html musí obsahovat kontaktní banner')
    if 'Exportovat' in cjs or 'export_archivnik' in cjs:
        fail('flow/customer-card.js nesmí obsahovat export')
    if 'app.js?v=p56a' not in html:
        fail('archivnik/index.html musí cache-bustovat app.js?v=p56a')
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description='P5.6A Archivník UI contract')
    parser.add_argument('--root', default='')
    args = parser.parse_args()
    root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parent.parent
    errors = check(root)
    if errors:
        print(f'FAIL  P5.6A UI contract ({root})')
        for item in errors:
            print(f'  - {item}')
        return 1
    print(f'OK    P5.6A UI contract ({root})')
    return 0


if __name__ == '__main__':
    sys.exit(main())
