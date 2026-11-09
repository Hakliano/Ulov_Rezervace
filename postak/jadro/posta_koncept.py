"""Rozepsané e-maily — pouze lokální DB."""

from __future__ import annotations

import os

from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

from .mail_sanitize import sanitize_html
from .models import EmailKoncept, EmailKonceptPriloha

MAX_UPLOAD = 10 * 1024 * 1024


class KonceptError(Exception):
    pass


def _koncept_uzivatele(request, pk):
    koncept = get_object_or_404(EmailKoncept, pk=pk)
    if koncept.vlastnik_id != request.user.id:
        raise PermissionDenied
    return koncept


def koncepty_uzivatele(user):
    return EmailKoncept.objects.filter(vlastnik=user).select_related('schranka').prefetch_related('prilohy')


def nacist_koncept(request, koncept_id, schranka):
    if not koncept_id:
        return None
    try:
        koncept_id = int(koncept_id)
    except (TypeError, ValueError):
        return None
    koncept = _koncept_uzivatele(request, koncept_id)
    if koncept.schranka_id != schranka.pk:
        raise KonceptError('Koncept patří jiné schránce.')
    return koncept


def koncept_do_initial(koncept: EmailKoncept):
    return {
        'komu': koncept.komu,
        'kopie': koncept.kopie,
        'skryte': koncept.skryte,
        'predmet': koncept.predmet,
        'telo': koncept.telo_html,
        'in_reply_to': koncept.in_reply_to or '',
    }


def _ulozit_prilohy(koncept, request):
    zachovat = {int(x) for x in request.POST.getlist('zachovat_priloha') if str(x).isdigit()}
    for pr in list(koncept.prilohy.all()):
        if pr.pk not in zachovat:
            pr.soubor.delete(save=False)
            pr.delete()
    for soubor in request.FILES.getlist('prilohy'):
        data = soubor.read(MAX_UPLOAD + 1)
        if len(data) > MAX_UPLOAD:
            raise KonceptError('Příloha je větší než 10 MB.')
        soubor.seek(0)
        EmailKonceptPriloha.objects.create(
            koncept=koncept,
            soubor=soubor,
            nazev=os.path.basename(soubor.name or 'priloha'),
            content_type=soubor.content_type or 'application/octet-stream',
            velikost=min(len(data), soubor.size or len(data)),
        )


def uloz_koncept(request, schranka, *, koncept_id=None):
    komu = request.POST.get('komu', '')
    koncept = None
    if koncept_id:
        koncept = _koncept_uzivatele(request, koncept_id)
        if koncept.schranka_id != schranka.pk:
            raise KonceptError('Koncept nelze uložit do jiné schránky.')
    else:
        koncept = EmailKoncept(vlastnik=request.user, schranka=schranka)
    koncept.komu = komu
    koncept.kopie = request.POST.get('kopie', '')
    koncept.skryte = request.POST.get('skryte', '')
    koncept.predmet = (request.POST.get('predmet', '') or '')[:500]
    koncept.telo_html = sanitize_html(request.POST.get('telo', ''))
    koncept.in_reply_to = (request.POST.get('in_reply_to', '') or '')[:300]
    koncept.save()
    _ulozit_prilohy(koncept, request)
    return koncept


def smaz_koncept(request, pk):
    koncept = _koncept_uzivatele(request, pk)
    for pr in koncept.prilohy.all():
        pr.soubor.delete(save=False)
    koncept.delete()


def prilohy_pro_odeslani(koncept: EmailKoncept):
    out = []
    for pr in koncept.prilohy.all():
        with pr.soubor.open('rb') as f:
            data = f.read()
        out.append((pr.nazev, data, pr.content_type))
    return out
