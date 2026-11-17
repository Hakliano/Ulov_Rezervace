from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from jadro.klienti_merge import modernik_patch_z_formulare
from jadro.klienti_models import KlientModernik
from jadro.klienti_sync import _delta_modernik, upsert_klient


def _mk_klient(**kw):
    kw.setdefault('stav', 'lead_pred_webu')
    kw.setdefault('stav_label', 'L')
    kw.setdefault('remote_upraveno', timezone.now())
    return KlientModernik.objects.create(**kw)


class KlientiMergeTests(TestCase):

    def test_prazdne_api_neprepise_web(self):
        _mk_klient(remote_id=1, jmeno='A', email='a@t.cz', web='https://example.test')
        upsert_klient({
            'id': 1,
            'jmeno': 'A',
            'email': 'a@t.cz',
            'web': '',
            'stav': 'klient',
            'stav_label': 'Klient',
            'upraveno': '2026-03-02T12:00:00+01:00',
        })
        k = KlientModernik.objects.get(remote_id=1)
        self.assertEqual(k.web, 'https://example.test')
        self.assertEqual(k.stav, 'klient')

    def test_stav_z_api_projde(self):
        _mk_klient(remote_id=2, jmeno='B', email='b@t.cz')
        upsert_klient({
            'id': 2,
            'jmeno': 'B',
            'email': 'b@t.cz',
            'stav': 'prodano',
            'stav_label': 'Prodáno',
            'upraveno': '2026-03-02T12:00:00+01:00',
        })
        self.assertEqual(KlientModernik.objects.get(remote_id=2).stav, 'prodano')

    def test_patch_jen_zmenena_pole(self):
        lokal = _mk_klient(
            remote_id=3,
            jmeno='C',
            email='c@t.cz',
            telefon='111',
            web='https://w.test',
        )
        class P:
            def __contains__(self, k):
                return k == 'telefon'
            def get(self, k, default=None):
                return '222' if k == 'telefon' else default
        patch, expected = modernik_patch_z_formulare(lokal, P())
        self.assertEqual(patch, {'telefon': '222'})
        self.assertEqual(expected, {'telefon': '111'})

    def test_patch_explicit_clear_web(self):
        lokal = _mk_klient(remote_id=4, jmeno='D', email='d@t.cz', web='https://w.test')
        class P:
            def __contains__(self, k):
                return k == 'web'
            def get(self, k, default=None):
                return '' if k == 'web' else default
        patch, _ = modernik_patch_z_formulare(lokal, P())
        self.assertIsNone(patch.get('web'))


class KlientiSyncNoDeleteTests(TestCase):
    @patch('jadro.klienti_sync.zmeny')
    def test_delta_nemaze_z_cache(self, api_zmeny):
        _mk_klient(remote_id=9, jmeno='Z', email='z@t.cz')
        api_zmeny.return_value = {
            'items': [],
            'deleted': [{'id': 9, 'smazano': '2026-03-02T12:00:00+01:00'}],
            'sektory': [],
            'server_time': '2026-03-02T13:00:00+01:00',
            'has_more': False,
        }
        stats = _delta_modernik(since='2026-03-01T11:00:00+01:00')
        self.assertEqual(stats['deleted'], 1)
        self.assertTrue(KlientModernik.objects.filter(remote_id=9).exists())