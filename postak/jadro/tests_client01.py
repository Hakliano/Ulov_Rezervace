from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from jadro.klienti_models import KlientModernik
from jadro.klienti_sync import upsert_klient

MAIL_KEY = '5UJw-fkaQCvOYE6rjCyROlCttrakyH3-D8Qieby3Mvc='


@override_settings(
    POSTAK_PREFIX='',
    POSTAK_MAIL_ENCRYPTION_KEY=MAIL_KEY,
    MODERNIK_API_BASE='http://test/api/postak/v1',
    MODERNIK_API_TOKEN='x',
)
class Client01Tests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('u', password='x')

    @patch('jadro.klienti_views._fetch_meta')
    def test_seznam_pro_prihlasene(self, meta):
        meta.return_value = ([], [], [])
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('klienti')).status_code, 200)

    @patch('jadro.klienti_views.api_vytvorit')
    @patch('jadro.klienti_views._fetch_meta')
    def test_zalozeni_pres_api(self, meta, vytvorit):
        meta.return_value = ([{'kod': 'lead_pred_webu', 'label': 'Lead'}], [], [])
        vytvorit.return_value = {
            'kontakt': {
                'id': 99,
                'jmeno': 'X',
                'email': 'x@test.cz',
                'telefon': '',
                'web': '',
                'adresa': '',
                'ico': '',
                'poznamka': '',
                'stav': 'lead_pred_webu',
                'stav_label': 'Lead',
                'sektor_id': None,
                'sektor_nazev': '',
                'vytvoreno': '2026-01-01T00:00:00+01:00',
                'upraveno': '2026-01-01T00:00:00+01:00',
            },
        }
        self.client.force_login(self.user)
        r = self.client.post(reverse('klient_novy'), {'jmeno': 'X', 'email': 'x@test.cz'})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(KlientModernik.objects.filter(remote_id=99).exists())

    def test_upsert_klient(self):
        upsert_klient({
            'id': 1,
            'jmeno': 'A',
            'email': 'a@t.cz',
            'stav': 'lead_pred_webu',
            'stav_label': 'L',
            'upraveno': '2026-03-01T12:00:00+01:00',
        })
        self.assertEqual(KlientModernik.objects.count(), 1)
