"""Lokální český kalendář jmenin — zdroj viz JMENINY_ZDROJ.md."""

from __future__ import annotations

import json
from datetime import date
from functools import lru_cache
from pathlib import Path

_DATA = Path(__file__).resolve().parent / 'data' / 'jmeniny_cz.json'


@lru_cache(maxsize=1)
def _kalendar() -> dict[str, list[str]]:
    with _DATA.open(encoding='utf-8') as f:
        raw = json.load(f)
    return {k: list(v) for k, v in raw.items()}


def jmeniny_pro_datum(d: date) -> list[str]:
    key = f'{int(d.month):02d}-{int(d.day):02d}'
    return list(_kalendar().get(key, []))


def jmeniny_pro_text(names: list[str]) -> str:
    return ', '.join(names)


def kalendar_json() -> dict[str, list[str]]:
    return _kalendar()
