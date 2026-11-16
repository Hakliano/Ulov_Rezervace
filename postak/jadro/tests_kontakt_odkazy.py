from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from jadro.klienti_models import KlientModernik
from jadro.klienti_sync import upsert_klient
from jadro.kontakt_odkazy import telefon_odkaz, web_odkaz


class KontaktOdkazyTests(TestCase):
    def test_web_doplni_https(self):
        w = web_odkaz('salon.cz')
        self.assertEqual(w['href'], 'https://salon.cz')

    def test_web_ponecha_http(self):
        w = web_odkaz('http://example.test/path')
        self.assertTrue(w['href'].startswith('http://'))

    def test_web_zablokuje_javascript(self):
        self.assertIsNone(web_odkaz('javascript:alert(1)'))

    def test_web_prazdny(self):
        self.assertIsNone(web_odkaz(''))
        self.assertIsNone(web_odkaz(None))

    def test_telefon_tel_href(self):
        t = telefon_odkaz('+420 777 111 222')
        self.assertEqual(t['href'], 'tel:+420777111222')
        self.assertIn('777', t['label'])

    def test_telefon_prazdny(self):
        self.assertIsNone(telefon_odkaz(''))


class KlientiSeznamUxTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('operator', password='heslo-12345')
        upsert_klient({
            'id': 99,
            'jmeno': 'Salon UX',
            'email': 'ux@test.cz',
            'telefon': '+420 603 842 823',
            'web': 'www.salon-ux.test',
            'stav': 'lead_pred_webu',
            'stav_label': 'Lead',
            'upraveno': '2026-03-01T12:00:00+01:00',
        })
        self.k = KlientModernik.objects.get(remote_id=99)

    def test_vypis_ma_web_a_tel_odkazy(self):
        self.client.force_login(self.user)
        html = self.client.get(reverse('klienti')).content.decode()
        self.assertIn('target="_blank"', html)
        self.assertIn('rel="noopener noreferrer"', html)
        self.assertIn('https://www.salon-ux.test', html)
        self.assertIn('tel:+420603842823', html)
        self.assertIn('603 842 823', html)