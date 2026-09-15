"""Centrální katalog oborových presetů. Živě se na tenant neváže — jen apply_preset kopíruje."""

from archivnik.presets.beauty import BEAUTY
from archivnik.presets.pneu import PNEU
from archivnik.presets.vet import VET

PRESETS = {
    VET['kod']: VET,
    BEAUTY['kod']: BEAUTY,
    PNEU['kod']: PNEU,
}


def list_presets():
    return [
        {
            'kod': row['kod'],
            'nazev': row['nazev'],
            'typy_pocet': len(row['typy']),
        }
        for row in PRESETS.values()
    ]


def get_preset(kod: str) -> dict:
    row = PRESETS.get((kod or '').strip())
    if not row:
        raise KeyError(kod)
    return row
