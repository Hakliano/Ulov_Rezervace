from django.apps import AppConfig


class PartnerAdminConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'partner_admin'
    verbose_name = 'Správa partnerů'

    def ready(self):
        from . import signals  # noqa: F401
