"""Přihlášení a odhlášení partner-admin — stejný vstup pro tým i superadmina."""
from django.conf import settings
from django.contrib.auth.views import LoginView, LogoutView
from django.http import HttpResponseRedirect

from .forms import PartnerAdminLoginForm
from .permissions import muze_do_panelu


class PartnerAdminLoginView(LoginView):
    template_name = 'partner_admin/login.html'
    authentication_form = PartnerAdminLoginForm
    redirect_authenticated_user = False

    def dispatch(self, request, *args, **kwargs):
        if muze_do_panelu(request.user):
            return HttpResponseRedirect(self.get_success_url())
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return self.get_redirect_url() or settings.LOGIN_REDIRECT_URL or '/partner-admin/'


class PartnerAdminLogoutView(LogoutView):
    next_page = '/partner-admin/login/'


prihlaseni = PartnerAdminLoginView.as_view()
odhlaseni = PartnerAdminLogoutView.as_view()
