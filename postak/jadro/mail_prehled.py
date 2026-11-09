"""Agregace nepřečtených e-mailů pro stránku Přehled — jen při jejím otevření."""

from __future__ import annotations

from django.conf import settings
from django.utils import timezone

from .mail_imap import MailError, overview_unseen
from .models import EmailSchranka


def _schranky_pro(request):
    qs = EmailSchranka.objects.prefetch_related('uzivatele')
    if request.user.is_superuser:
        return qs
    return qs.filter(uzivatele=request.user)


def email_prehled(request):
    timeout = getattr(settings, 'POSTAK_MAIL_OVERVIEW_TIMEOUT', 8)
    limit = getattr(settings, 'POSTAK_MAIL_OVERVIEW_LIMIT', 8)
    schranky = list(_schranky_pro(request))
    if not schranky:
        return {
            'pocet': 0,
            'polozky': [],
            'chyby': [],
            'stav': 'bez_schranky',
            'cas': None,
        }

    pocet = 0
    polozky = []
    chyby = []
    for schranka in schranky:
        try:
            info = overview_unseen(schranka, timeout=timeout, limit=limit)
            pocet += info['count']
            for row in info['items']:
                polozky.append({
                    **row,
                    'schranka_id': schranka.pk,
                    'schranka_email': schranka.email,
                })
        except MailError as exc:
            chyby.append(f'{schranka.email}: {exc}')
        except Exception:
            chyby.append(f'{schranka.email}: nepředvídatelná chyba IMAP.')

    polozky.sort(key=lambda r: r.get('uid', 0), reverse=True)
    polozky = polozky[:limit]

    cas = timezone.now()
    uspesne = len(schranky) - len(chyby)
    if uspesne == 0:
        stav = 'nepristupne'
    elif chyby:
        stav = 'castecne'
    else:
        stav = 'ok'
    return {
        'pocet': pocet if uspesne else None,
        'polozky': polozky if uspesne else [],
        'chyby': chyby,
        'stav': stav,
        'cas': cas,
    }
