from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from jadro.jmeniny import jmeniny_pro_datum, jmeniny_pro_text

MAIL_KEY = '5UJw-fkaQCvOYE6rjCyROlCttrakyH3-D8Qieby3Mvc='


@override_settings(POSTAK_PREFIX='', POSTAK_MAIL_ENCRYPTION_KEY=MAIL_KEY)
class Ux02Tests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('u', password='x')
        self.client.force_login(self.user)

    def test_uvitaci_text(self):
        r = self.client.get(reverse('prehled'))
        self.assertContains(r, 'Vítejte v Pošťákovi!')
        self.assertNotContains(r, 'Vítejte v Pošťáku!')

    def test_banner_prvky(self):
        r = self.client.get(reverse('prehled'))
        self.assertContains(r, 'id="dash-clock"')
        self.assertContains(r, 'Dnes má svátek')
        self.assertContains(r, 'postak_banner.js')
        self.assertContains(r, 'dash-hero')

    def test_nav_tlacitka_prehled(self):
        r = self.client.get(reverse('prehled'))
        self.assertContains(r, 'btn secondary btn-small')
        self.assertContains(r, '>Kalendář</a>')

    def test_jmeniny_kontrolni_data(self):
        self.assertIn('Horymír', jmeniny_pro_datum(date(2024, 2, 29)))
        self.assertIn('Karina', jmeniny_pro_datum(date(2026, 1, 2)))
        self.assertIn('Bedřich', jmeniny_pro_datum(date(2025, 3, 1)))
        self.assertIn('Silvestr', jmeniny_pro_datum(date(2025, 12, 31)))
        vic = jmeniny_pro_datum(date(2026, 2, 5))
        self.assertGreaterEqual(len(vic), 2)
        self.assertIn('Dobromila', jmeniny_pro_text(vic))

    def test_jmeniny_bez_stavu(self):
        self.assertEqual(jmeniny_pro_datum(date(2026, 1, 1)), [])

    def test_nav_tlacitka_email_ucty(self):
        su = User.objects.create_superuser('su', password='x')
        self.client.force_login(su)
        r = self.client.get(reverse('email_ucty'))
        self.assertContains(r, 'btn secondary btn-small')
        self.assertContains(r, 'Nastavení')
