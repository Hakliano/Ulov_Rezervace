from django.shortcuts import redirect
from django.urls import Resolver404, resolve, reverse

from .models import Profil


class VynutitZmenuHeslaMiddleware:
    """Po dočasném hesle směruje na nastavení (změna hesla)."""

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
        user = getattr(request, 'user', None)
        if user and user.is_authenticated:
            try:
                profil = user.profil
            except Profil.DoesNotExist:
                profil = None
            if profil and profil.vyzadovat_zmenu_hesla:
                try:
                    name = resolve(request.path_info).url_name or ''
                except Resolver404:
                    name = ''
                if name not in self.POVOLENE:
                    return redirect(reverse('nastaveni'))
        return self.get_response(request)
