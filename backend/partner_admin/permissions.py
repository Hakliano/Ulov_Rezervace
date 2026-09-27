"""Oprávnění partner-admin: superuser, nebo staff s rolí kam / admin_finance."""
from functools import wraps

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponseForbidden


FORBIDDEN = 0
READ = 1
WRITE = 2

ROLE_KAM = 'kam'
ROLE_ADMIN_FINANCE = 'admin_finance'

LOGIN_URL = '/partner-admin/login/'
SAFE_METHODS = frozenset({'GET', 'HEAD', 'OPTIONS'})

PREHLED = 'prehled'
PARTNERI = 'partneri'
TESTOVACI = 'testovaci_pristupy'
PLATBY = 'platby'
FAKTURY = 'faktury'
CHYBY = 'chyby'
NOVY_PARTNER = 'novy_partner'
TARIFY = 'tarify'
KAM = 'kam'
POTENCIALNI = 'potencialni'
UCTY = 'ucty'
VYDAJE = 'vydaje'
EMAILY = 'emaily'
DJANGO_ADMIN = 'django_admin'
TYM = 'tym'
BLOKACE = 'blokace'
RESET_HESLA = 'reset_hesla'

ZASOBY = (
    PREHLED,
    PARTNERI,
    TESTOVACI,
    PLATBY,
    FAKTURY,
    CHYBY,
    NOVY_PARTNER,
    TARIFY,
    KAM,
    POTENCIALNI,
    UCTY,
    VYDAJE,
    EMAILY,
    DJANGO_ADMIN,
    TYM,
    BLOKACE,
    RESET_HESLA,
)

_KAM = {
    PREHLED: READ,
    PARTNERI: WRITE,
    TESTOVACI: WRITE,
    PLATBY: FORBIDDEN,
    FAKTURY: READ,
    CHYBY: READ,
    NOVY_PARTNER: WRITE,
    TARIFY: READ,
    KAM: READ,
    POTENCIALNI: WRITE,
    UCTY: FORBIDDEN,
    VYDAJE: FORBIDDEN,
    EMAILY: FORBIDDEN,
    DJANGO_ADMIN: FORBIDDEN,
    TYM: FORBIDDEN,
    BLOKACE: FORBIDDEN,
    RESET_HESLA: FORBIDDEN,
}

_ADMIN_FINANCE = {
    PREHLED: READ,
    PARTNERI: WRITE,
    TESTOVACI: READ,
    PLATBY: WRITE,
    FAKTURY: WRITE,
    CHYBY: READ,
    NOVY_PARTNER: FORBIDDEN,
    TARIFY: WRITE,
    KAM: WRITE,
    POTENCIALNI: WRITE,
    UCTY: WRITE,
    VYDAJE: WRITE,
    EMAILY: FORBIDDEN,
    DJANGO_ADMIN: FORBIDDEN,
    TYM: FORBIDDEN,
    BLOKACE: FORBIDDEN,
    RESET_HESLA: FORBIDDEN,
}

_MAPA = {
    ROLE_KAM: _KAM,
    ROLE_ADMIN_FINANCE: _ADMIN_FINANCE,
}

_ROLE_LABEL = {
    ROLE_KAM: 'KAM',
    ROLE_ADMIN_FINANCE: 'ADMIN/Finance',
}


class OpravneniPriznaky:
    """Šablony: {% if pa_can_write.platby %}."""

    def __init__(self, hodnoty):
        self.__dict__.update(hodnoty)


def partner_admin_profil(user):
    if not user or not getattr(user, 'is_authenticated', False):
        return None
    try:
        return user.partner_admin_profil
    except (ObjectDoesNotExist, AttributeError):
        return None


def muze_do_panelu(user):
    if not user or not getattr(user, 'is_authenticated', False) or not user.is_active:
        return False
    if user.is_superuser:
        return True
    return bool(user.is_staff and partner_admin_profil(user))


def role_uzivatele(user):
    if not user or not getattr(user, 'is_authenticated', False):
        return ''
    if user.is_superuser:
        return 'superuser'
    profil = partner_admin_profil(user)
    return profil.role if profil else ''


def role_label(user):
    if not user or not getattr(user, 'is_authenticated', False):
        return ''
    if user.is_superuser:
        return 'Superadmin'
    profil = partner_admin_profil(user)
    if not profil:
        return ''
    return _ROLE_LABEL.get(profil.role, profil.get_role_display())


def zobrazovane_jmeno(user):
    profil = partner_admin_profil(user)
    if profil and profil.jmeno:
        return profil.jmeno
    if not user:
        return ''
    return user.get_full_name() or user.username


def uroven_opravneni(user, zasob):
    if not muze_do_panelu(user):
        return FORBIDDEN
    if user.is_superuser:
        return WRITE
    profil = partner_admin_profil(user)
    if not profil:
        return FORBIDDEN
    return _MAPA.get(profil.role, {}).get(zasob, FORBIDDEN)


def muze_videt(user, zasob):
    return uroven_opravneni(user, zasob) >= READ


def muze_zapisovat(user, zasob):
    return uroven_opravneni(user, zasob) >= WRITE


def priznaky(user, minimum):
    return OpravneniPriznaky({
        zasob: uroven_opravneni(user, zasob) >= minimum
        for zasob in ZASOBY
    })


def partner_admin_perm(zasob):
    """Superuser vždy. Tým: GET 403 pokud forbidden, POST 403 pokud read/forbidden."""

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            user = request.user
            login_url = getattr(settings, 'LOGIN_URL', LOGIN_URL) or LOGIN_URL
            if not getattr(user, 'is_authenticated', False) or not user.is_active:
                return redirect_to_login(request.get_full_path(), login_url)
            if not muze_do_panelu(user):
                return redirect_to_login(request.get_full_path(), login_url)
            uroven = uroven_opravneni(user, zasob)
            if uroven == FORBIDDEN:
                return HttpResponseForbidden('Nemáte oprávnění k této stránce.')
            if request.method not in SAFE_METHODS and uroven < WRITE:
                return HttpResponseForbidden('Tato akce je jen pro čtení, nebo k ní nemáte oprávnění.')
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator
