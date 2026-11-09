from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from .mail_forms import PodpisForm, SchrankaForm, SchrankaPristupForm
from .mail_sanitize import sanitize_html
from .mail_secrets import MailDecryptError, decrypt_secret
from .mail_test import test_imap, test_smtp
from .models import EmailSchranka
from .views import login_required_view, superuser_required


def _schranky_pro(request):
    qs = EmailSchranka.objects.prefetch_related('uzivatele')
    if request.user.is_superuser:
        return qs
    return qs.filter(uzivatele=request.user)


def _zobrazitelna(request, schranka):
    if request.user.is_superuser:
        return True
    return schranka.uzivatele.filter(pk=request.user.pk).exists()


@login_required_view
def email_ucty(request):
    return render(request, 'email_ucty.html', {
        'schranky': _schranky_pro(request),
        'muze_spravovat': request.user.is_superuser,
    })


@superuser_required
@require_http_methods(['GET', 'POST'])
def email_ucet_novy(request):
    form = SchrankaForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        schranka = form.save()
        messages.success(request, f'Schránka {schranka.email} je uložená.')
        return redirect('email_ucet_detail', pk=schranka.pk)
    return render(request, 'email_ucet_form.html', {'form': form, 'nadpis': 'Nová schránka'})


@login_required_view
@require_http_methods(['GET', 'POST'])
def email_ucet_detail(request, pk):
    schranka = get_object_or_404(EmailSchranka, pk=pk)
    if not _zobrazitelna(request, schranka):
        raise PermissionDenied

    if request.method == 'POST' and not request.user.is_superuser:
        raise PermissionDenied

    form = SchrankaForm(request.POST or None, instance=schranka) if request.user.is_superuser else None
    pristup_form = SchrankaPristupForm(
        request.POST or None,
        initial={'uzivatele': schranka.uzivatele.all()},
    ) if request.user.is_superuser else None
    podpis_form = PodpisForm(
        request.POST or None,
        initial={'podpis_html': schranka.podpis_html},
    ) if request.user.is_superuser else None

    if request.method == 'POST':
        akce = request.POST.get('akce') or ''
        if akce == 'ulozit' and form and form.is_valid():
            schranka = form.save()
            messages.success(request, 'Konfigurace schránky je uložená.')
            return redirect('email_ucet_detail', pk=schranka.pk)
        if akce == 'podpis' and podpis_form and podpis_form.is_valid():
            schranka.podpis_html = sanitize_html(podpis_form.cleaned_data['podpis_html'] or '')
            schranka.save(update_fields=['podpis_html', 'upraveno'])
            messages.success(request, 'Podpis schránky je uložený.')
            return redirect('email_ucet_detail', pk=schranka.pk)
        if akce == 'pristup' and pristup_form and pristup_form.is_valid():
            schranka.uzivatele.set(pristup_form.cleaned_data['uzivatele'])
            messages.success(request, 'Přidělení uživatelů je uložené.')
            return redirect('email_ucet_detail', pk=schranka.pk)
        if akce == 'odpojit':
            email = schranka.email
            schranka.delete()
            messages.success(request, f'Schránka {email} je odpojená.')
            return redirect('email_ucty')
        raise Http404

    return render(request, 'email_ucet_detail.html', {
        'schranka': schranka,
        'form': form,
        'pristup_form': pristup_form,
        'podpis_form': podpis_form,
        'muze_spravovat': request.user.is_superuser,
    })


@login_required_view
@require_POST
def email_ucet_test(request, pk):
    if not request.user.is_superuser:
        raise PermissionDenied
    schranka = get_object_or_404(EmailSchranka, pk=pk)
    try:
        heslo = decrypt_secret(schranka.heslo_sifra)
    except MailDecryptError:
        messages.error(request, 'Heslo schránky nejde načíst. Uložte ho znovu.')
        return redirect('email_ucet_detail', pk=pk)
    if not heslo:
        messages.error(request, 'Schránka nemá uložené heslo.')
        return redirect('email_ucet_detail', pk=pk)

    user = schranka.prihlasovaci_jmeno or schranka.email
    imap = test_imap(
        host=schranka.imap_host,
        port=schranka.imap_port,
        use_ssl=schranka.imap_ssl,
        user=user,
        password=heslo,
    )
    smtp = test_smtp(
        host=schranka.smtp_host,
        port=schranka.smtp_port,
        use_ssl=schranka.smtp_ssl,
        starttls=schranka.smtp_starttls,
        user=user,
        password=heslo,
    )
    ok = imap.ok and smtp.ok
    info = []
    info.append(imap.detail)
    info.append(smtp.detail)
    schranka.test_stav = EmailSchranka.STAV_OK if ok else EmailSchranka.STAV_CHYBA
    schranka.test_info = ' '.join(info)[:300]
    schranka.testovano = timezone.now()
    schranka.save(update_fields=['test_stav', 'test_info', 'testovano', 'upraveno'])

    if ok:
        messages.success(request, 'IMAP i SMTP přihlášení proběhlo v pořádku.')
    else:
        messages.warning(request, schranka.test_info)
    return redirect('email_ucet_detail', pk=pk)
