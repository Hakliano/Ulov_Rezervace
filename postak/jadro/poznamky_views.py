from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET

from .mail_sanitize import html_to_plain
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from .mail_sanitize import sanitize_html
from .models import PoznamkaKoncept
from .views import login_required_view

RAZENI = {
    'poradi': ('poradi', 'nazev'),
    'nazev': ('nazev', 'poradi'),
    'upraveno': ('-upraveno', 'poradi'),
}


def _vlastnik_poznamka(request, pk):
    poz = get_object_or_404(PoznamkaKoncept, pk=pk)
    if poz.vlastnik_id != request.user.id:
        raise PermissionDenied
    return poz


def _obsah_z_post(request):
    raw = request.POST.get('obsah_html', '')
    return sanitize_html(raw)


@login_required_view
def poznamky_seznam(request):
    razeni = request.GET.get('razeni') or 'poradi'
    order = RAZENI.get(razeni, RAZENI['poradi'])
    polozky = PoznamkaKoncept.objects.filter(vlastnik=request.user).order_by(*order)
    return render(request, 'poznamky_seznam.html', {
        'polozky': polozky,
        'razeni': razeni,
    })


@login_required_view
@require_http_methods(['GET', 'POST'])
def poznamka_nova(request):
    initial = {'nazev': '', 'poradi': 0, 'obsah_html': ''}
    if request.method == 'POST':
        nazev = (request.POST.get('nazev') or '').strip()[:200]
        if not nazev:
            messages.error(request, 'Vyplňte název.')
            initial = {
                'nazev': request.POST.get('nazev', ''),
                'poradi': request.POST.get('poradi', 0),
                'obsah_html': request.POST.get('obsah_html', ''),
            }
        else:
            try:
                poradi = int(request.POST.get('poradi') or 0)
            except ValueError:
                poradi = 0
            poz = PoznamkaKoncept.objects.create(
                vlastnik=request.user,
                nazev=nazev,
                poradi=poradi,
                obsah_html=_obsah_z_post(request),
            )
            messages.success(request, 'Záznam je uložený.')
            return redirect('poznamka_detail', pk=poz.pk)
    return render(request, 'poznamka_edit.html', {
        'poznamka': None,
        'initial': initial,
        'nova': True,
    })


@login_required_view
@require_http_methods(['GET', 'POST'])
def poznamka_detail(request, pk):
    poz = _vlastnik_poznamka(request, pk)
    if request.method == 'POST':
        nazev = (request.POST.get('nazev') or '').strip()[:200]
        if not nazev:
            messages.error(request, 'Vyplňte název.')
        else:
            try:
                poradi = int(request.POST.get('poradi') or 0)
            except ValueError:
                poradi = poz.poradi
            poz.nazev = nazev
            poz.poradi = poradi
            poz.obsah_html = _obsah_z_post(request)
            poz.save()
            messages.success(request, 'Záznam je uložený.')
            return redirect('poznamka_detail', pk=poz.pk)
    return render(request, 'poznamka_edit.html', {
        'poznamka': poz,
        'initial': {
            'nazev': poz.nazev,
            'poradi': poz.poradi,
            'obsah_html': poz.obsah_html,
        },
        'nova': False,
    })


@login_required_view
@require_GET
def poznamka_kopirovat_data(request, pk):
    poz = _vlastnik_poznamka(request, pk)
    plain = html_to_plain(poz.obsah_html)
    return JsonResponse({'html': poz.obsah_html, 'plain': plain})


@login_required_view
@require_POST
def poznamka_smazat(request, pk):
    poz = _vlastnik_poznamka(request, pk)
    poz.delete()
    messages.success(request, 'Záznam je smazaný.')
    return redirect('poznamky')
