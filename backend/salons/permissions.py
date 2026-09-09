from django.conf import settings
from rest_framework.permissions import BasePermission

from partner_hub.models import get_partner_user
from rezervace.services.staff_auth import get_staff_from_request, je_majitel


def _legacy_admin_password(request):
    """Jen lokální DEBUG. V produkci globální bypass neexistuje."""
    if not settings.DEBUG:
        return False
    expected = (getattr(settings, 'SALON_ADMIN_PASSWORD', '') or '').strip()
    if not expected:
        return False
    got = (request.headers.get('X-Admin-Password') or '').strip()
    if not got:
        return False
    return got == expected


def _partner_ok(request):
    return get_partner_user(request) is not None


def _django_superuser(request):
    user = getattr(request, 'user', None)
    return bool(user and user.is_authenticated and user.is_active and user.is_superuser)


class StaffPermission(BasePermission):
    """Vyžaduje přihlášeného zaměstnance (token), partner hub, nebo legacy heslo salonu."""

    def has_permission(self, request, view):
        if _django_superuser(request) or _partner_ok(request):
            return True
        salon_id = view.kwargs.get('pk') or view.kwargs.get('salon_id')
        if get_staff_from_request(request, salon_id):
            return True
        return _legacy_admin_password(request)


class MajitelPermission(BasePermission):
    """Pouze majitel/majitelka salonu, partner hub, Django superuser, nebo legacy admin heslo."""

    def has_permission(self, request, view):
        if _django_superuser(request) or _partner_ok(request):
            return True
        salon_id = view.kwargs.get('pk') or view.kwargs.get('salon_id')
        staff = get_staff_from_request(request, salon_id)
        if je_majitel(staff):
            return True
        return _legacy_admin_password(request)


class AdminPasswordPermission(BasePermission):
    """Čtení veřejné; zápis vyžaduje přihlášení personálu / partnera / superusera."""

    def has_permission(self, request, view):
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        if _django_superuser(request) or _partner_ok(request):
            return True
        salon_id = view.kwargs.get('pk')
        if get_staff_from_request(request, salon_id):
            return True
        return _legacy_admin_password(request)
