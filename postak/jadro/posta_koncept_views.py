from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .mail_views import _zobrazitelna
from .models import EmailSchranka
from .posta_koncept import koncepty_uzivatele, smaz_koncept
from .views import login_required_view


@login_required_view
def posta_koncepty(request):
    return render(request, 'posta_koncepty.html', {
        'koncepty': koncepty_uzivatele(request.user),
    })


@login_required_view
@require_POST
def posta_koncept_smazat(request, pk):
    smaz_koncept(request, pk)
    messages.success(request, 'Koncept je smazaný.')
    return redirect('posta_koncepty')


@login_required_view
def posta_koncept_upravit(request, pk):
    from .posta_koncept import _koncept_uzivatele

    koncept = _koncept_uzivatele(request, pk)
    schranka = koncept.schranka
    if not _zobrazitelna(request, schranka):
        raise PermissionDenied
    return redirect(f"{reverse('posta_napsat', args=[schranka.pk])}?koncept={koncept.pk}")
