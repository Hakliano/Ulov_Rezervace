from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

HESLO = 'Spravne-heslo-1'


@override_settings(POSTAK_PREFIX='')
class Help01Tests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('eva', password=HESLO)
        self.admin = User.objects.create_user('admin', password=HESLO, is_superuser=True)

    def test_napoveda_vyzaduje_prihlaseni(self):
        url = reverse('napoveda')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/prihlaseni/', response.url)

    def test_tlacitko_na_prehledu(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('prehled'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'NÁPOVĚDA')
        self.assertContains(response, reverse('napoveda'))

    def test_stranka_napoveda_obsah(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('napoveda'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Jak používat Pošťáka?')
        self.assertContains(response, 'id="prehled"')
        self.assertContains(response, 'id="emaily"')
        self.assertContains(response, reverse('emaily'))
        self.assertContains(response, 'Zpět na Přehled')

    def test_bezny_uzivatel_nevidi_spravu(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('napoveda'))
        self.assertNotContains(response, 'id="sprava"')
        self.assertNotContains(response, 'Správa uživatelů – Pouze pro správce')

    def test_superuser_vidi_spravu(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('napoveda'))
        self.assertContains(response, 'id="sprava"')
        self.assertContains(response, 'Odeslat přihlašovací údaje')
        self.assertContains(response, reverse('email_ucty'))
        self.assertContains(response, reverse('uzivatele'))

    def test_karty_odkazuji_na_kapitoly(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('napoveda'))
        self.assertContains(response, 'href="#kalendar"')
        self.assertContains(response, 'help-cards')
