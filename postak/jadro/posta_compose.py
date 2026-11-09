import secrets
from urllib.parse import urlencode

from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .mail_compose_body import quote_forward_html, quote_reply_html
from .mail_imap import MailError, get_detail
from .mail_send import send_message
from .posta_koncept import (
    KonceptError,
    koncept_do_initial,
    nacist_koncept,
    prilohy_pro_odeslani,
    smaz_koncept,
    uloz_koncept,
)
from .posta_views import _schranka
from .views import login_required_view

MAX_UPLOAD = 10 * 1024 * 1024


def _qs(folder, koncept_id=''):
    data = {}
    if folder:
        data['slozka'] = folder
    if koncept_id:
        data['koncept'] = koncept_id
    return urlencode(data)


@login_required_view
@require_http_methods(['GET', 'POST'])
def posta_napsat(request, pk, mode='new', uid=0):
    schranka = _schranka(request, pk)
    folder = request.GET.get('slozka') or 'INBOX'
    koncept = None
    initial = {
        'komu': '',
        'kopie': '',
        'skryte': '',
        'predmet': '',
        'telo': '',
        'in_reply_to': '',
    }
    koncept_id = request.GET.get('koncept') or request.POST.get('koncept_id')
    try:
        koncept = nacist_koncept(request, koncept_id, schranka)
    except KonceptError as exc:
        messages.error(request, str(exc))
        koncept = None
        koncept_id = ''

    if koncept:
        initial = koncept_do_initial(koncept)
    elif mode != 'new' and uid:
        try:
            detail = get_detail(schranka, folder=folder, uid=uid, mark_seen=False)
        except MailError as exc:
            messages.error(request, str(exc))
            return redirect('posta_seznam', pk=pk)
        subj = detail['subject'] or ''
        if not subj.lower().startswith('re:') and mode in ('reply', 'reply_all'):
            subj = f'Re: {subj}'
        if not subj.lower().startswith('fwd:') and mode == 'forward':
            subj = f'Fwd: {subj}'
        body = ''
        if mode == 'forward':
            body = quote_forward_html(
                from_=detail['from'],
                to=detail.get('to', '') or '',
                subject=detail['subject'] or '',
                body_text=detail['body_text'] or '',
            )
        elif mode == 'reply':
            body = quote_reply_html(author=detail['from'], body_text=detail['body_text'] or '')
            initial['komu'] = detail.get('reply_to') or detail['from']
        elif mode == 'reply_all':
            body = quote_reply_html(author=detail['from'], body_text=detail['body_text'] or '')
            initial['komu'] = detail.get('reply_to') or detail['from']
            if detail.get('to'):
                initial['kopie'] = detail['to']
        initial.update({
            'predmet': subj,
            'telo': body,
            'in_reply_to': detail.get('message_id', ''),
        })

    if request.method == 'POST':
        akce = request.POST.get('akce') or 'odeslat'
        if akce == 'koncept':
            try:
                kid = request.POST.get('koncept_id') or koncept_id
                saved = uloz_koncept(request, schranka, koncept_id=kid or None)
                messages.success(request, 'Koncept je uložený.')
                return redirect(
                    f"{reverse('posta_napsat', args=[pk])}?{_qs(folder, saved.pk)}"
                )
            except KonceptError as exc:
                messages.error(request, str(exc))
                initial = {
                    'komu': request.POST.get('komu', ''),
                    'kopie': request.POST.get('kopie', ''),
                    'skryte': request.POST.get('skryte', ''),
                    'predmet': request.POST.get('predmet', ''),
                    'telo': request.POST.get('telo', ''),
                    'in_reply_to': request.POST.get('in_reply_to', ''),
                }
        else:
            token = request.session.pop('posta_otp', '')
            if token != (request.POST.get('otp') or ''):
                messages.error(request, 'Odeslání bylo již zpracováno nebo vypršelo. Zkuste znovu.')
                return redirect(f"{reverse('posta_napsat', args=[pk])}?{_qs(folder, koncept_id)}")
            kid = request.POST.get('koncept_id') or koncept_id
            ulozeny = None
            if kid:
                try:
                    ulozeny = nacist_koncept(request, kid, schranka)
                except KonceptError:
                    ulozeny = None
            try:
                attachments = []
                if ulozeny:
                    attachments.extend(prilohy_pro_odeslani(ulozeny))
                for soubor in request.FILES.getlist('prilohy'):
                    data = soubor.read(MAX_UPLOAD + 1)
                    if len(data) > MAX_UPLOAD:
                        raise MailError('Příloha je větší než 10 MB.')
                    attachments.append((soubor.name, data, soubor.content_type or 'application/octet-stream'))
                send_message(
                    schranka,
                    to=request.POST.get('komu', ''),
                    cc=request.POST.get('kopie', ''),
                    bcc=request.POST.get('skryte', ''),
                    subject=request.POST.get('predmet', ''),
                    body=request.POST.get('telo', ''),
                    attachments=attachments,
                    in_reply_to=request.POST.get('in_reply_to', ''),
                )
                if kid:
                    smaz_koncept(request, kid)
                messages.success(request, 'Zpráva je odeslaná.')
                return redirect('posta_seznam', pk=pk)
            except MailError as exc:
                messages.error(request, str(exc))
                initial = {
                    'komu': request.POST.get('komu', ''),
                    'kopie': request.POST.get('kopie', ''),
                    'skryte': request.POST.get('skryte', ''),
                    'predmet': request.POST.get('predmet', ''),
                    'telo': request.POST.get('telo', ''),
                    'in_reply_to': request.POST.get('in_reply_to', ''),
                }
                koncept_id = kid or koncept_id
                if kid:
                    try:
                        koncept = nacist_koncept(request, kid, schranka)
                    except KonceptError:
                        koncept = None

    request.session['posta_otp'] = secrets.token_hex(16)
    return render(request, 'posta_napsat.html', {
        'schranka': schranka,
        'mode': mode,
        'initial': initial,
        'otp': request.session['posta_otp'],
        'folder': folder,
        'uid': uid,
        'koncept': koncept,
        'koncept_id': (koncept.pk if koncept else koncept_id) or '',
    })
