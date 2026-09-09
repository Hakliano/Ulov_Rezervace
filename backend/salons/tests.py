from django.test import TestCase, Client, override_settings

from salons.models import Salon


class LegacyAdminPasswordTests(TestCase):
    def setUp(self):
        self.salon = Salon.objects.create(name='Legacy Bypass Salon')
        self.email_url = f'/api/salon/{self.salon.id}/admin/email/'
        self.login_url = '/api/auth/login/'
        self.client = Client()

    @override_settings(DEBUG=False, SALON_ADMIN_PASSWORD='admin123')
    def test_production_ignores_legacy_header_even_if_env_set(self):
        res = self.client.get(self.email_url, HTTP_X_ADMIN_PASSWORD='admin123')
        self.assertIn(res.status_code, (401, 403))

    @override_settings(DEBUG=False, SALON_ADMIN_PASSWORD='admin123')
    def test_production_auth_login_is_gone(self):
        res = self.client.post(
            self.login_url,
            data={'password': 'admin123'},
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 404)

    @override_settings(DEBUG=True, SALON_ADMIN_PASSWORD='lokální-tajne')
    def test_debug_legacy_header_still_works(self):
        res = self.client.get(self.email_url, HTTP_X_ADMIN_PASSWORD='lokální-tajne')
        self.assertEqual(res.status_code, 200)

    @override_settings(DEBUG=True, SALON_ADMIN_PASSWORD='')
    def test_debug_empty_password_never_matches(self):
        res = self.client.get(self.email_url, HTTP_X_ADMIN_PASSWORD='')
        self.assertIn(res.status_code, (401, 403))
