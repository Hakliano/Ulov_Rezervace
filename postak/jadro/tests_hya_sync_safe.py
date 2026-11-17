from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from jadro.klienti_hya_merge import defaults_from_hya_api, hya_patch_z_formulare
from jadro.klienti_models import KlientHya
from jadro.klienti_sync import _delta_hya, upsert_klient_hya
from jadro.obchodni_stavy import kanon_z_api_stavu


def _mk(**kw):
    kw.setdefault('stav', 'lead_pred_webu')
    kw.setdefault('stav_label', 'L')
    kw.setdefault('remote_upraveno', timezone.now())
    return KlientHya.objects.create(**kw)


class HyaSyncSafeTests(TestCase):
    def test_sync_mapuje_stav_do_kanonu(self):
        upsert_klient_hya({
            'id': 1,
            'company_name': 'A',
            'email': 'a@t.cz',
            'status': 'sold',
            'updated_on': '2026-03-02T12:00:00+01:00',
        })
        self.assertEqual(KlientHya.objects.get(remote_id=1).stav, 'prodano')

    def test_prazdne_api_neprepise_web(self):
        _mk(remote_id=2, jmeno='B', email='b@t.cz', web='https://x.test')
        upsert_klient_hya({
            'id': 2,
            'company_name': 'B',
            'email': 'b@t.cz',
            'status': 'lead_before_web',
            'web': '',
            'updated_on': '2026-03-02T12:00:00+01:00',
        })
        self.assertEqual(KlientHya.objects.get(remote_id=2).web, 'https://x.test')

    @patch('jadro.klienti_sync.hya_zmeny', return_value={'results': [], 'has_more': False})
    @patch('jadro.klienti_sync.hya_smazane')
    def test_delta_nemaze_cache(self, smazane, *_):
        smazane.return_value = {
            'deletions': [{'id': 9, 'deleted_at': '2026-03-02T12:00:00+01:00'}],
            'has_more': False,
        }
        _mk(remote_id=9, jmeno='Z', email='z@t.cz')
        stats = _delta_hya('2026-03-01T11:00:00+01:00')
        self.assertEqual(stats['deleted'], 1)
        self.assertTrue(KlientHya.objects.filter(remote_id=9).exists())

    def test_patch_status_posle_hya_api_kod(self):
        loc = _mk(remote_id=3, jmeno='C', email='c@t.cz', stav='ma_zajem')

        class P:
            def __contains__(self, k):
                return k == 'stav'
            def get(self, k, default=None):
                return 'prodano' if k == 'stav' else default

        patch, expected = hya_patch_z_formulare(loc, P())
        self.assertEqual(patch['status'], 'sold')
        self.assertEqual(expected['status'], 'interested')
        self.assertEqual(kanon_z_api_stavu(defaults_from_hya_api({'id': 3, 'status': 'sold'})['stav']), 'prodano')