from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from jadro.hya_client import HyaApiError
from jadro.klienti_constants import PROJEKT_HYA, PROJEKT_MODERNIK
from jadro.klienti_models import KlientHya, KlientModernik
from jadro.klienti_sync import synchronizuj_hya, synchronizuj_klienty, synchronizuj_modernik, upsert_klient_hya

MAIL_KEY = '5UJw-fkaQCvOYE6rjCyROlCttrakyH3-D8Qieby3Mvc='

HYA_CLIENT = {
    'id': 7,
    'company_name': 'Chata API',
    'email': 'hya@test.cz',
    'phone': '+420777000111',
    'status': 'lead_before_web',
    'updated_on': '2026-03-10T12:00:00+01:00',
}


@override_settings(
    POSTAK_PREFIX='',
    POSTAK_MAIL_ENCRYPTION_KEY=MAIL_KEY,
    MODERNIK_API_BASE='http://test/api/postak/v1',
    MODERNIK_API_TOKEN='x',
    HYA_API_BASE='http://test/hya/internal/postak/v1',
    HYA_POSTAK_API_TOKEN='hya-token',
)
class Client01BTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('u', password='x')
        self.client.force_login(self.user)

    def test_upsert_hya(self):
        upsert_klient_hya(HYA_CLIENT)
        self.assertEqual(KlientHya.objects.get().jmeno, 'Chata API')

    @patch('jadro.klienti_sync._delta_modernik', return_value={'updated': 1, 'deleted': 0, 'cursor': '2026-03-10T12:00:00+01:00'})
    @patch('jadro.klienti_sync._bootstrap_modernik', return_value=False)
    def test_sync_modernik_nezavisle(self, *_):
        stats = synchronizuj_modernik()
        self.assertTrue(stats['ok'])

    @patch('jadro.klienti_sync._delta_hya', return_value={'updated': 2, 'deleted': 1, 'cursor': '2026-03-10T12:00:00+01:00'})
    @patch('jadro.klienti_sync._bootstrap_hya', return_value=False)
    def test_sync_hya_nezavisle(self, *_):
        stats = synchronizuj_hya()
        self.assertTrue(stats['ok'])

    @patch('jadro.klienti_sync.synchronizuj_hya')
    @patch('jadro.klienti_sync.synchronizuj_modernik')
    def test_sync_spolecne(self, m_mod, m_hya):
        m_mod.return_value = {'ok': True, 'updated': 0, 'deleted': 0, 'error': ''}
        m_hya.return_value = {'ok': False, 'updated': 0, 'deleted': 0, 'error': 'vypnuto'}
        out = synchronizuj_klienty()
        self.assertTrue(out['modernik']['ok'])
        self.assertFalse(out['hya']['ok'])

    @patch('jadro.klienti_views._fetch_meta', return_value=([], [], []))
    def test_seznam_bez_smazat(self, *_):
        r = self.client.get(reverse('klienti'))
        self.assertNotContains(r, 'Smazat')
        self.assertContains(r, 'HereYouAre')

    @patch('jadro.klienti_views.hya_upravit')
    @patch('jadro.klienti_views._fetch_meta')
    def test_hya_conflict_409(self, meta, upravit):
        meta.return_value = ([], [{'kod': 'lead_before_web', 'label': 'Lead'}], [])
        upsert_klient_hya(HYA_CLIENT)
        lokal = KlientHya.objects.get()
        upravit.side_effect = HyaApiError(
            'konflikt',
            status=409,
            code='conflict',
            payload={'client': {**HYA_CLIENT, 'phone': '+420777999888'}},
        )
        r = self.client.post(
            reverse('klient_detail', args=[PROJEKT_HYA, lokal.pk]),
            {'jmeno': 'Chata API', 'telefon': '+420777111222', 'email': 'hya@test.cz'},
        )
        self.assertEqual(r.status_code, 200)
        lokal.refresh_from_db()
        self.assertEqual(lokal.telefon, '+420777999888')

    @patch('jadro.klienti_views.hya_vytvorit')
    @patch('jadro.klienti_views._fetch_meta')
    def test_zalozeni_hya(self, meta, vytvorit):
        meta.return_value = ([], [{'kod': 'lead_before_web', 'label': 'Lead'}], [])
        vytvorit.return_value = {'client': HYA_CLIENT}
        r = self.client.post(
            reverse('klient_novy'),
            {'projekt': PROJEKT_HYA, 'jmeno': 'Chata', 'email': 'hya@test.cz'},
        )
        self.assertEqual(r.status_code, 302)
        self.assertTrue(KlientHya.objects.filter(remote_id=7).exists())

    @patch('jadro.klienti_views._fetch_meta')
    def test_filtr_projekt(self, meta):
        meta.return_value = ([], [], [])
        KlientModernik.objects.create(
            remote_id=1,
            jmeno='Mod',
            email='m@t.cz',
            stav='lead_pred_webu',
            stav_label='L',
            remote_upraveno='2026-01-01T00:00:00+01:00',
        )
        KlientHya.objects.create(
            remote_id=1,
            jmeno='Hya',
            email='h@t.cz',
            stav='lead_before_web',
            stav_label='L',
            remote_upraveno='2026-01-02T00:00:00+01:00',
        )
        r = self.client.get(reverse('klienti'), {'projekt': PROJEKT_HYA})
        self.assertContains(r, 'Hya')
        self.assertNotContains(r, '>Mod<')
