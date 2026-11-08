from functools import wraps

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView, LogoutView, redirect_to_login
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .forms import HesloUzivateleForm, NovyUzivatelForm, PrihlaseniForm, VlastniHesloForm

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
    karty = [
        ('E-maily', 'Zatím bez zpráv.', 'emaily'),
        ('Úkoly', 'Zatím bez úkolů.', 'kalendar'),
        ('Moderník', 'Zatím bez klientů.', 'klienti'),
        ('HereYouAre', 'Zatím bez klientů.', 'klienti'),
    ]
    return render(request, 'prehled.html', {'karty': karty})


@login_required_view
def prazdna(request, klic):
    nadpis, popis = SEKCE[klic]
    return render(request, 'prazdna.html', {'nadpis': nadpis, 'popis': popis})


@login_required_view
@require_http_methods(['GET', 'POST'])
def nastaveni(request):
    form = VlastniHesloForm(request.user, request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        messages.success(request, 'Heslo je změněné.')
        return redirect('nastaveni')
    return render(request, 'nastaveni.html', {'form': form})


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
    if request.method == 'POST':
        akce = request.POST.get('akce') or ''
        if akce == 'heslo':
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
        'posledni': _posledni_aktivni_superuser(cil),
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
