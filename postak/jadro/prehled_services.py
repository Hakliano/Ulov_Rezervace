"""Agregace pro dashboard Přehled — pouze lokální cache."""

from django.db.models import Count

from .klienti_constants import PROJEKT_HYA, PROJEKT_MODERNIK
from .klienti_models import KlientHya, KlientModernik


def statistiky_klientu():
    mod = KlientModernik.objects.count()
    hya = KlientHya.objects.count()
    return {
        'celkem': mod + hya,
        'modernik': mod,
        'hya': hya,
    }


def pipeline_klientu(projekt='vse'):
    projekt = (projekt or 'vse').strip().lower()
    if projekt not in ('vse', PROJEKT_MODERNIK, PROJEKT_HYA):
        projekt = 'vse'
    bars = []
    if projekt in ('vse', PROJEKT_MODERNIK):
        rows = (
            KlientModernik.objects.values('stav', 'stav_label')
            .annotate(pocet=Count('id'))
            .order_by('-pocet', 'stav')
        )
        for row in rows:
            label = (row['stav_label'] or row['stav'] or '?').strip()
            bars.append({
                'projekt': PROJEKT_MODERNIK,
                'projekt_label': 'Moderník',
                'stav': row['stav'],
                'label': label,
                'zobrazit': f'Moderník — {label}',
                'pocet': row['pocet'],
            })
    if projekt in ('vse', PROJEKT_HYA):
        rows = (
            KlientHya.objects.values('stav', 'stav_label')
            .annotate(pocet=Count('id'))
            .order_by('-pocet', 'stav')
        )
        for row in rows:
            label = (row['stav_label'] or row['stav'] or '?').strip()
            bars.append({
                'projekt': PROJEKT_HYA,
                'projekt_label': 'HereYouAre',
                'stav': row['stav'],
                'label': label,
                'zobrazit': f'HereYouAre — {label}',
                'pocet': row['pocet'],
            })
    peak = max((b['pocet'] for b in bars), default=0)
    cap = peak or 1
    for bar in bars:
        bar['sirka'] = round(100 * bar['pocet'] / cap)
    return bars, projekt
