from django.contrib import messages
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from .chat_services import (
    kolegove_s_meta,
    konverzace,
    muze_chatovat,
    odeslat,
    oznac_prectene,
    profil_telefon,
)
from .views import login_required_view


@login_required_view
def tym_seznam(request):
    return render(request, 'tym_seznam.html', {
        'kolegove_meta': kolegove_s_meta(request.user),
    })


@login_required_view
@require_http_methods(['GET', 'POST'])
def tym_konverzace(request, pk):
    partner = get_object_or_404(User, pk=pk)
    if not partner.is_active and request.method == 'POST':
        messages.error(request, 'Deaktivovanému uživateli nelze posílat zprávy.')
        return redirect('tym_konverzace', pk=pk)
    if request.method == 'POST':
        try:
            odeslat(request.user, partner, request.POST.get('text', ''))
            return redirect('tym_konverzace', pk=pk)
        except ValueError as exc:
            messages.error(request, str(exc))
    oznac_prectene(request.user, partner)
    zpravy = list(konverzace(request.user, partner))
    return render(request, 'tym_chat.html', {
        'partner': partner,
        'partner_telefon': profil_telefon(partner),
        'zpravy': zpravy,
        'muze_psat': muze_chatovat(request.user, partner),
        'kolegove_meta': kolegove_s_meta(request.user),
    })


@login_required_view
@require_POST
def tym_sync(request, pk):
    get_object_or_404(User, pk=pk)
    messages.success(request, 'Konverzace je aktualizovaná.')
    return redirect('tym_konverzace', pk=pk)
