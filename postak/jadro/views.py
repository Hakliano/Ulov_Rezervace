from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView, LogoutView, redirect_to_login
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .chat_services import pocet_neprectenych, posledni_neprectene
from .kalendar_services import dnesni_program, moje_ukoly
from .jmeniny import jmeniny_pro_datum, jmeniny_pro_text, kalendar_json
from .prehled_services import pipeline_klientu, statistiky_klientu
from .forms import (
    HesloUzivateleForm,
    NovyUzivatelForm,
    OdeslatPrihlasovaciForm,
    PrihlaseniForm,
    ProfilForm,
    UcetForm,
    VlastniHesloForm,
)
from .user_credentials import odeslat_prihlasovaci_udaje, prihlasovaci_email_uzivatele
from .user_credentials_models import OdeslaniPrihlasovacich
from .mail_prehled import email_prehled
from .models import Profil
from .obrazky import PRIPONY, pripona_obrazku

SEKCE = {
    'emaily': (
        'E-maily',
        'Schránky a zprávy přibudou později. Teď tu žádná pošta není.',
    ),
    'klienti': (
        'Potenciální klienti',
        'Propojení s Moderníkem a HereYouAre přijde později. Seznam je zatím prázdný.',
    ),
    'kalendar': (
        'Kalendář',
        'Události, úkoly a připomínky přibudou později. Kalendář je zatím prázdný.',
    ),
    'dokumentace': (
        'Dokumentace',
        'Složky a soubory přibudou později. Knihovna je zatím prázdná.',
    ),
}


def _posledni_aktivni_superuser(cil):
    if not (cil.is_superuser and cil.is_active):
        return False
    return not User.objects.filter(is_superuser=True, is_active=True).exclude(pk=cil.pk).exists()


def login_required_view(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), login_url=reverse('prihlaseni'))
        return view(request, *args, **kwargs)
    return wrapper


def superuser_required(view):
    @wraps(view)
    @login_required_view
    def wrapper(request, *args, **kwargs):
        if not request.user.is_superuser:
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapper


class PostakLogin(LoginView):
    template_name = 'prihlaseni.html'
    authentication_form = PrihlaseniForm
    redirect_authenticated_user = True
    next_page = 'prehled'


class PostakLogout(LogoutView):
    next_page = 'prihlaseni'


@login_required_view
def prehled(request):
    email = email_prehled(request)
    chat_pocet = pocet_neprectenych(request.user)
    chat_polozky = posledni_neprectene(request.user, limit=5)
    ukoly, ukoly_po_terminu = moje_ukoly(request.user)
    pipeline, pipeline_filtr = pipeline_klientu(request.GET.get('pipeline'))
    jmeniny = jmeniny_pro_datum(timezone.localdate())
    return render(request, 'prehled.html', {
        'email_prehled': email,
        'chat_pocet': chat_pocet,
        'chat_polozky': chat_polozky,
        'dnes_program': dnesni_program(request.user),
        'ukoly': ukoly,
        'ukoly_po_terminu': ukoly_po_terminu,
        'klienti_stats': statistiky_klientu(),
        'pipeline': pipeline,
        'pipeline_filtr': pipeline_filtr,
        'dnes_datum': timezone.localdate(),
        'jmeniny_dnes': jmeniny,
        'jmeniny_text': jmeniny_pro_text(jmeniny),
        'jmeniny_kalendar': kalendar_json(),
    })


@login_required_view
def napoveda(request):
    return render(request, 'napoveda.html', {
        'je_superuser': request.user.is_superuser,
    })


@login_required_view
def prazdna(request, klic):
    nadpis, popis = SEKCE[klic]
    return render(request, 'prazdna.html', {'nadpis': nadpis, 'popis': popis})


@login_required_view
@require_http_methods(['GET', 'POST'])
def nastaveni(request):
    heslo_form = VlastniHesloForm(request.user)
    profil_form = ProfilForm(user=request.user)
    if request.method == 'POST':
        akce = request.POST.get('akce') or ''
        if akce == 'heslo':
            heslo_form = VlastniHesloForm(request.user, request.POST)
            if heslo_form.is_valid():
                user = heslo_form.save()
                update_session_auth_hash(request, user)
                profil, _ = Profil.objects.get_or_create(user=user)
                if profil.vyzadovat_zmenu_hesla:
                    profil.vyzadovat_zmenu_hesla = False
                    profil.save(update_fields=['vyzadovat_zmenu_hesla'])
                messages.success(request, 'Heslo je změněné.')
                return redirect('nastaveni')
        elif akce == 'profil':
            profil_form = ProfilForm(request.POST, request.FILES, user=request.user)
            if profil_form.is_valid():
                profil_form.save()
                messages.success(request, 'Profil je uložený.')
                return redirect('nastaveni')
        else:
            raise Http404
    profil, _ = Profil.objects.get_or_create(user=request.user)
    return render(request, 'nastaveni.html', {
        'form': heslo_form,
        'profil_form': profil_form,
        'vyzadovat_zmenu_hesla': profil.vyzadovat_zmenu_hesla,
    })


@login_required_view
def profil_foto(request, pk):
    if request.user.pk != pk and not request.user.is_superuser:
        raise PermissionDenied
    profil = get_object_or_404(Profil, user_id=pk)
    if not profil.foto:
        raise Http404
    try:
        with profil.foto.open('rb') as handle:
            data = handle.read()
    except FileNotFoundError:
        raise Http404 from None
    pripona = pripona_obrazku(data[:16])
    if pripona not in PRIPONY:
        raise Http404
    response = HttpResponse(data, content_type=PRIPONY[pripona])
    response['X-Content-Type-Options'] = 'nosniff'
    response['Content-Disposition'] = 'inline'
    response['Cache-Control'] = 'private, max-age=3600'
    return response


@superuser_required
def uzivatele(request):
    return render(request, 'uzivatele.html', {
        'uzivatele': User.objects.order_by('username'),
    })


@superuser_required
@require_http_methods(['GET', 'POST'])
def uzivatel_novy(request):
    form = NovyUzivatelForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        messages.success(request, f'Uživatel {user.username} je vytvořený.')
        return redirect('uzivatele')
    return render(request, 'uzivatel_novy.html', {'form': form})


@superuser_required
@require_http_methods(['GET', 'POST'])
def uzivatel_detail(request, pk):
    cil = get_object_or_404(User, pk=pk)
    heslo_form = HesloUzivateleForm(cil)
    ucet_form = UcetForm(user=cil)
    if request.method == 'POST':
        akce = request.POST.get('akce') or ''
        if akce == 'ucet':
            ucet_form = UcetForm(request.POST, user=cil)
            if ucet_form.is_valid():
                ucet_form.save()
                messages.success(request, 'Údaje uživatele jsou uložené.')
                return redirect('uzivatel_detail', pk=cil.pk)
        elif akce == 'heslo':
            heslo_form = HesloUzivateleForm(cil, request.POST)
            if heslo_form.is_valid():
                heslo_form.save()
                messages.success(request, 'Heslo uživatele je změněné.')
                return redirect('uzivatel_detail', pk=cil.pk)
        elif akce == 'role':
            _zmenit_roli(request, cil)
            return redirect('uzivatel_detail', pk=cil.pk)
        elif akce in ('aktivovat', 'deaktivovat'):
            _zmenit_aktivitu(request, cil, akce == 'aktivovat')
            return redirect('uzivatel_detail', pk=cil.pk)
        else:
            raise Http404
    return render(request, 'uzivatel_detail.html', {
        'cil': cil,
        'heslo_form': heslo_form,
        'ucet_form': ucet_form,
        'posledni': _posledni_aktivni_superuser(cil),
        'login_id': prihlasovaci_email_uzivatele(cil),
    })


@superuser_required
@require_http_methods(['GET', 'POST'])
def uzivatel_odeslat_prihlasovaci(request, pk):
    cil = get_object_or_404(User, pk=pk)
    form = OdeslatPrihlasovaciForm(request.POST or None, cil_user=cil)
    login_id = prihlasovaci_email_uzivatele(cil)
    potvrzeni_text = (
        f'Na zadanou adresu budou odeslány přístupové údaje k účtu „{login_id}“. '
        'Bude vygenerováno nové dočasné heslo.'
    )
    if request.method == 'POST' and form.is_valid():
        zaznam = odeslat_prihlasovaci_udaje(
            cil=cil,
            odeslal=request.user,
            prijemce=form.cleaned_data['prijemce'],
        )
        if zaznam.uspech:
            messages.success(request, f'Přihlašovací údaje byly odeslány na {zaznam.prijemce}.')
            return redirect('uzivatel_detail', pk=cil.pk)
        messages.error(request, zaznam.chyba or 'Odeslání se nepodařilo. Heslo uživatele nebylo změněno.')
    historie = list(
        OdeslaniPrihlasovacich.objects.filter(cilovy_uzivatel=cil).order_by('-vytvoreno')[:5],
    )
    return render(request, 'uzivatel_odeslat_prihlasovaci.html', {
        'cil': cil,
        'form': form,
        'login_id': login_id,
        'potvrzeni_text': potvrzeni_text,
        'historie': historie,
    })


def _zmenit_roli(request, cil):
    role = request.POST.get('role')
    if role not in ('user', 'superuser'):
        messages.error(request, 'Neznámá role.')
        return
    if role != 'superuser' and _posledni_aktivni_superuser(cil):
        messages.error(request, 'Poslednímu aktivnímu SUPERUSEROVI roli neodeberete.')
        return
    cil.is_superuser = role == 'superuser'
    cil.save(update_fields=['is_superuser'])
    messages.success(request, 'Role je uložená.')


def _zmenit_aktivitu(request, cil, aktivni):
    if not aktivni and cil.pk == request.user.pk:
        messages.error(request, 'Svůj účet nedeaktivujete.')
        return
    if not aktivni and _posledni_aktivni_superuser(cil):
        messages.error(request, 'Posledního aktivního SUPERUSERA nelze deaktivovat.')
        return
    cil.is_active = aktivni
    cil.save(update_fields=['is_active'])
    messages.success(request, 'Účet je aktivní.' if aktivni else 'Účet je deaktivovaný.')
