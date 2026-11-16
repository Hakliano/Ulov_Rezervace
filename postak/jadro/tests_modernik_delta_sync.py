from unittest.mock import patch

from django.test import TestCase

from jadro.klienti_models import KlientModernik
from jadro.klienti_sync import _delta_modernik, upsert_klient


class ModernikDeltaSyncTests(TestCase):
    @patch('jadro.klienti_sync.zmeny')
    def test_delta_prochazi_strankami(self, api_zmeny):
        upsert_klient({
            'id': 1, 'jmeno': 'A', 'email': 'a@t.cz', 'stav': 'lead_pred_webu',
            'stav_label': 'L', 'upraveno': '2026-03-01T12:00:00+01:00',
        })
        start = KlientModernik.objects.count()

        def page(since=None, limit=500, offset=0):
            if offset == 0:
                return {
                    'items': [{'id': 2, 'jmeno': 'B', 'email': 'b@t.cz', 'stav': 'lead_pred_webu', 'stav_label': 'L', 'upraveno': '2026-03-02T12:00:00+01:00'}],
                    'deleted': [],
                    'sektory': [],
                    'server_time': '2026-03-02T13:00:00+01:00',
                    'has_more': True,
                    'next_offset': 1,
                }
            return {
                'items': [{'id': 3, 'jmeno': 'C', 'email': 'c@t.cz', 'stav': 'lead_pred_webu', 'stav_label': 'L', 'upraveno': '2026-03-03T12:00:00+01:00'}],
                'deleted': [],
                'sektory': [],
                'server_time': '2026-03-03T13:00:00+01:00',
                'has_more': False,
                'next_offset': 2,
            }

        api_zmeny.side_effect = page
        stats = _delta_modernik(since='2026-03-01T11:00:00+01:00')
        self.assertEqual(stats['updated'], 2)
        self.assertEqual(KlientModernik.objects.count(), start + 2)
        self.assertEqual(KlientModernik.objects.filter(remote_id=1).get().stav, 'lead_pred_webu')