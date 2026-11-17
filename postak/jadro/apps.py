from django.apps import AppConfig


class JadroConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'jadro'
    verbose_name = 'Pošťák'

    def ready(self):
        from django.conf import settings

        import jadro.user_activity  # noqa: F401 — user_logged_in

        if settings.configured and getattr(settings, 'POSTAK_STAGING_MODE', False):
            from jadro.staging_api_guard import assert_staging_crm_targets

            assert_staging_crm_targets()
