"""Evidence přihlášení a poslední aktivity uživatele."""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from django.urls import Resolver404, get_script_prefix, resolve
from django.utils import timezone

from .models import Profil
from .user_credentials_models import PrihlaseniHistorie

AKTIVITA_THROTTLE_SEC = 60
ONLINE_MINUT = 5
HISTORIE_PRIHLASENI_DNI = 30


def smaz_stara_prihlaseni():
    hranice = timezone.now() - timedelta(days=HISTORIE_PRIHLASENI_DNI)
    PrihlaseniHistorie.objects.filter(vytvoreno__lt=hranice).delete()


def historie_prihlaseni(uzivatel):
    smaz_stara_prihlaseni()
    hranice = timezone.now() - timedelta(days=HISTORIE_PRIHLASENI_DNI)
    return PrihlaseniHistorie.objects.filter(uzivatel=uzivatel, vytvoreno__gte=hranice)


def uzivatel_je_online(profil: Profil | None) -> bool:
    if not profil or not profil.posledni_aktivita:
        return False
    return profil.posledni_aktivita >= timezone.now() - timedelta(minutes=ONLINE_MINUT)


def zapis_posledni_aktivitu(user) -> None:
    if not user or not user.is_authenticated:
        return
    now = timezone.now()
    profil, _ = Profil.objects.get_or_create(user=user)
    if profil.posledni_aktivita:
        delta = (now - profil.posledni_aktivita).total_seconds()
        if delta < AKTIVITA_THROTTLE_SEC:
            return
    Profil.objects.filter(pk=profil.pk).update(posledni_aktivita=now)


@receiver(user_logged_in)
def zaznamenat_prihlaseni(sender, request, user, **kwargs):
    smaz_stara_prihlaseni()
    PrihlaseniHistorie.objects.create(uzivatel=user)


class ZapisPosledniAktivityMiddleware:
    """Maximálně jeden UPDATE za minutu na přihlášeného uživatele."""

    POVOLENE = frozenset({
        'nastaveni',
        'napoveda',
        'odhlaseni',
        'prihlaseni',
        'profil_foto',
    })

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        user = getattr(request, 'user', None)
        if user and user.is_authenticated:
            if not self._sledovat_request(request):
                return response
            zapis_posledni_aktivitu(user)
        return response

    def _sledovat_request(self, request) -> bool:
        path = request.path_info or ''
        prefix = (getattr(request, 'script_prefix', None) or get_script_prefix() or '').rstrip('/')
        if prefix and path.startswith(prefix + '/static/'):
            return False
        if '/static/' in path:
            return False
        try:
            name = resolve(request.path_info).url_name or ''
        except Resolver404:
            name = ''
        if name in self.POVOLENE and request.method == 'GET':
            return False
        return True