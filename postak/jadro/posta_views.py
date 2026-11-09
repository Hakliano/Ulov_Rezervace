from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST
from urllib.parse import urlencode

from .mail_actions import delete_permanent, is_trash_folder, move_to_trash, restore_messages, set_seen
from .mail_imap import (
    MailError,
    STRANKA_VELIKOST,
    fetch_attachment,
    get_detail,
    list_folders,
    list_page,
    refresh_folder,
)
from .mail_views import _schranky_pro, _zobrazitelna
from .models import EmailSchranka
from .views import login_required_view


def _schranka(request, pk):
    schranka = get_object_or_404(EmailSchranka, pk=pk)
    if not _zobrazitelna(request, schranka):
        raise PermissionDenied
    return schranka


@login_required_view
def posta_seznam(request, pk):
    schranka = _schranka(request, pk)
    folder = request.GET.get('slozka') or 'INBOX'
    page = request.GET.get('stranka') or 1
    chyba = ''
    slozky = []
    prehled = None
    try:
        slozky = list_folders(schranka)
        names = {s['name'] for s in slozky}
        if folder not in names:
            folder = 'INBOX'
        prehled = list_page(schranka, folder=folder, page=page, per_page=STRANKA_VELIKOST)
    except MailError as exc:
        chyba = str(exc)
    schranky = _schranky_pro(request)
    in_trash = is_trash_folder(schranka, folder)
    return render(request, 'posta_seznam.html', {
        'schranka': schranka,
        'schranky': schranky,
        'slozky': slozky,
        'folder': folder,
        'prehled': prehled,
        'chyba': chyba,
        'in_trash': in_trash,
    })


@login_required_view
def posta_vstup(request):
    schranky = _schranky_pro(request)
    first = schranky.first()
    if not first:
        return render(request, 'posta_prazdna.html')
    return redirect('posta_seznam', pk=first.pk)


def _qs(folder, stranka, uv):
    return urlencode({'slozka': folder, 'stranka': stranka, 'uv': uv})


@login_required_view
@require_http_methods(['GET', 'POST'])
def posta_zprava(request, pk, uid):
    schranka = _schranka(request, pk)
    folder = request.GET.get('slozka') or request.POST.get('slozka') or 'INBOX'
    uidvalidity = request.GET.get('uv') or request.POST.get('uv') or ''
    stranka = request.GET.get('stranka') or request.POST.get('stranka') or 1
    if request.method == 'POST':
        akce = request.POST.get('akce') or ''
        try:
            if akce == 'seen_on':
                set_seen(schranka, folder=folder, uid=uid, seen=True)
            elif akce == 'seen_off':
                set_seen(schranka, folder=folder, uid=uid, seen=False)
            elif akce == 'trash':
                move_to_trash(schranka, folder=folder, uids=[uid])
                messages.success(request, 'Zpráva je v koši.')
                return redirect(f"{reverse('posta_seznam', args=[pk])}?{_qs('INBOX', stranka, uidvalidity)}")
            elif akce == 'restore':
                restore_messages(schranka, folder=folder, uids=[uid])
                messages.success(request, 'Zpráva je obnovená.')
                return redirect(f"{reverse('posta_seznam', args=[pk])}?{_qs(folder, stranka, uidvalidity)}")
            elif akce == 'delete' and is_trash_folder(schranka, folder):
                delete_permanent(schranka, folder=folder, uids=[uid])
                messages.success(request, 'Zpráva je trvale smazaná.')
                return redirect(f"{reverse('posta_seznam', args=[pk])}?{_qs(folder, stranka, uidvalidity)}")
        except MailError as exc:
            messages.error(request, str(exc))
    chyba = ''
    detail = None
    try:
        detail = get_detail(
            schranka,
            folder=folder,
            uid=uid,
            mark_seen=(request.method == 'GET'),
            uidvalidity=uidvalidity,
        )
    except MailError as exc:
        chyba = str(exc)
    return render(request, 'posta_zprava.html', {
        'schranka': schranka,
        'folder': folder,
        'stranka': stranka,
        'uidvalidity': uidvalidity or (detail or {}).get('uidvalidity', ''),
        'zprava': detail,
        'chyba': chyba,
        'in_trash': is_trash_folder(schranka, folder),
    })


@login_required_view
@require_POST
def posta_sync(request, pk):
    schranka = _schranka(request, pk)
    folder = request.POST.get('slozka') or 'INBOX'
    stranka = request.POST.get('stranka') or 1
    try:
        info = refresh_folder(schranka, folder=folder)
        messages.success(
            request,
            f'Schránka {schranka.email} · složka „{folder}“ je aktualizovaná (UIDVALIDITY {info["uidvalidity"]}).',
        )
        uv = info['uidvalidity']
    except MailError as exc:
        messages.error(request, str(exc))
        uv = request.POST.get('uv') or ''
    return redirect(f"{reverse('posta_seznam', args=[pk])}?{_qs(folder, stranka, uv)}")


@login_required_view
@require_POST
def posta_akce(request, pk):
    schranka = _schranka(request, pk)
    folder = request.POST.get('slozka') or 'INBOX'
    stranka = request.POST.get('stranka') or 1
    uv = request.POST.get('uv') or ''
    uids = request.POST.getlist('uid')
    akce = request.POST.get('akce') or ''
    try:
        if akce == 'trash':
            move_to_trash(schranka, folder=folder, uids=uids)
            messages.success(request, 'Vybrané zprávy jsou v koši.')
        elif akce == 'restore':
            restore_messages(schranka, folder=folder, uids=uids)
            messages.success(request, 'Vybrané zprávy jsou obnovené.')
        elif akce == 'delete' and is_trash_folder(schranka, folder):
            delete_permanent(schranka, folder=folder, uids=uids)
            messages.success(request, 'Vybrané zprávy jsou trvale smazané.')
        elif akce == 'seen_on':
            for uid in uids:
                set_seen(schranka, folder=folder, uid=uid, seen=True)
        elif akce == 'seen_off':
            for uid in uids:
                set_seen(schranka, folder=folder, uid=uid, seen=False)
        else:
            messages.error(request, 'Neznámá akce.')
    except MailError as exc:
        messages.error(request, str(exc))
    return redirect(f"{reverse('posta_seznam', args=[pk])}?{_qs(folder, stranka, uv)}")


@login_required_view
def posta_priloha(request, pk, uid, part):
    schranka = _schranka(request, pk)
    folder = request.GET.get('slozka') or 'INBOX'
    uidvalidity = request.GET.get('uv') or ''
    try:
        data, name, ctype = fetch_attachment(
            schranka,
            folder=folder,
            uid=uid,
            part_no=part,
            uidvalidity=uidvalidity,
        )
    except MailError as exc:
        raise Http404 from exc
    response = HttpResponse(data, content_type=ctype)
    response['Content-Disposition'] = f'attachment; filename="{name}"'
    response['X-Content-Type-Options'] = 'nosniff'
    return response

