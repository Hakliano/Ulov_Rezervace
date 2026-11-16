from django.test import TestCase

from jadro.klienti_models import KlientHya, KlientModernik
from jadro.klienti_sync import upsert_klient, upsert_klient_hya


class PartnerGeoSyncTests(TestCase):
    def test_upsert_modernik_nova_pole(self):
        upsert_klient({
            'id': 5,
            'jmeno': 'X',
            'email': 'x@t.cz',
            'stav': 'lead_pred_webu',
            'stav_label': 'L',
            'mesto': 'Plzeň',
            'latitude': '49.5',
            'longitude': '0',
            'upraveno': '2026-03-01T12:00:00+01:00',
        })
        k = KlientModernik.objects.get(remote_id=5)
        self.assertEqual(k.mesto, 'Plzeň')

    def test_gps_nula_v_cache(self):
        upsert_klient({
            'id': 6,
            'jmeno': 'Y',
            'email': 'y@t.cz',
            'stav': 'lead_pred_webu',
            'stav_label': 'L',
            'latitude': '0',
            'longitude': '0',
            'upraveno': '2026-03-01T12:00:00+01:00',
        })
        k = KlientModernik.objects.get(remote_id=6)
        self.assertIsNone(k.latitude)
        self.assertIsNone(k.longitude)

    def test_hya_sync_netknuta(self):
        upsert_klient_hya({
            'id': 1,
            'company_name': 'H',
            'email': 'h@t.cz',
            'status': 'lead_before_web',
            'updated_on': '2026-03-01T12:00:00+01:00',
        })
        self.assertEqual(KlientHya.objects.count(), 1)
        self.assertFalse('mesto' in [f.name for f in KlientHya._meta.get_fields()])