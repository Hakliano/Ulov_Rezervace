from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

HESLO = 'Spravne-heslo-1'


@override_settings(POSTAK_PREFIX='')
class PrihlaseniEmailTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('Muller', password=HESLO, email='muller@modernik.cz')
        self.url = reverse('prihlaseni')

    def _prihlasit(self, ident):
        return self.client.post(self.url, {'username': ident, 'password': HESLO})

    def test_jmeno_funguje(self):
        response = self._prihlasit('Muller')
        self.assertRedirects(response, reverse('prehled'))

    def test_email_funguje(self):
        response = self._prihlasit('muller@modernik.cz')
        self.assertRedirects(response, reverse('prehled'))

    def test_email_bez_ohledu_na_velikost_pismen(self):
        response = self._prihlasit('MULLER@MODERNIK.CZ')
        self.assertRedirects(response, reverse('prehled'))

    def test_duplicitni_email_odmitne(self):
        User.objects.create_user('druhy', password=HESLO, email='muller@modernik.cz')
        response = self._prihlasit('muller@modernik.cz')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Neplatné jméno nebo heslo.')

    def test_popisek_pole(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'E-mail nebo uživatelské jméno')
