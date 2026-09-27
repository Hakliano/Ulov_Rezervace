from django.apps import AppConfig


class PartnerAdminConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'partner_admin'
    verbose_name = 'Správa partnerů'

    def ready(self):
        from django.contrib import admin
        from django.http import HttpResponseRedirect

        from . import signals  # noqa: F401

        admin.site.has_permission = lambda request: bool(
            getattr(request, 'user', None)
            and request.user.is_active
            and request.user.is_superuser
        )

        if getattr(admin.site, '_ulov_team_login_wrapped', False):
            return

        _original_login = admin.site.login

        def _login(request, extra_context=None):
            from django.contrib.auth.views import redirect_to_login

            user = getattr(request, 'user', None)
            if (
                user is not None
                and user.is_authenticated
                and user.is_active
                and not user.is_superuser
            ):
                return HttpResponseRedirect('/partner-admin/')
            if not (user is not None and getattr(user, 'is_authenticated', False)):
                next_url = request.GET.get('next') or '/partner-admin/'
                return redirect_to_login(next_url, '/partner-admin/login/')
            return _original_login(request, extra_context=extra_context)

        admin.site.login = _login
        admin.site._ulov_team_login_wrapped = True
