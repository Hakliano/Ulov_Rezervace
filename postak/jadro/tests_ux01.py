from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from jadro.klienti_constants import PROJEKT_HYA, PROJEKT_MODERNIK
from jadro.klienti_models import KlientHya, KlientModernik
from jadro.prehled_services import pipeline_klientu, statistiky_klientu

MAIL_KEY = '5UJw-fkaQCvOYE6rjCyROlCttrakyH3-D8Qieby3Mvc='


@override_settings(POSTAK_PREFIX='', POSTAK_MAIL_ENCRYPTION_KEY=MAIL_KEY)
class Ux01Tests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('ux', password='x')

    def test_statistiky_realna_data(self):
        now = timezone.now()
        KlientModernik.objects.create(
            remote_id=1, jmeno='A', email='a@t.cz', stav='novy', stav_label='Nový', remote_upraveno=now,
        )
        KlientHya.objects.create(
            remote_id=2, jmeno='B', stav='lead', stav_label='Lead', remote_upraveno=now,
        )
        s = statistiky_klientu()
        self.assertEqual(s['celkem'], 2)
        self.assertEqual(s['modernik'], 1)
        self.assertEqual(s['hya'], 1)

    def test_pipeline_rozlisuje_projekty(self):
        now = timezone.now()
        KlientModernik.objects.create(
            remote_id=10, jmeno='M', email='m@t.cz', stav='s1', stav_label='Stav M', remote_upraveno=now,
        )
        KlientHya.objects.create(
            remote_id=11, jmeno='H', stav='s2', stav_label='Stav H', remote_upraveno=now,
        )
        bars, filtr = pipeline_klientu('vse')
        self.assertEqual(filtr, 'vse')
        labels = [b['zobrazit'] for b in bars]
        self.assertTrue(any('Moderník' in x for x in labels))
        self.assertTrue(any('HereYouAre' in x for x in labels))
        bars_m, filtr_m = pipeline_klientu(PROJEKT_MODERNIK)
        self.assertEqual(filtr_m, PROJEKT_MODERNIK)
        self.assertTrue(all(b['projekt'] == PROJEKT_MODERNIK for b in bars_m))

    def test_prehled_dashboard(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse('prehled'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Vítejte v Pošťákovi!')
        self.assertContains(r, 'Obchodní pipeline')
        self.assertContains(r, 'Potenciální klienti')

    def test_prehled_pipeline_filter(self):
        self.client.force_login(self.user)
        self.assertContains(
            self.client.get(reverse('prehled'), {'pipeline': 'modernik'}),
            'Moderník',
        )

    def test_nova_udalost_datum_prefill(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse('kalendar_nova'), {'datum': '2026-11-12'})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, '2026-11-12')

    def test_nova_neplatne_datum(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse('kalendar_nova'), {'datum': 'not-a-date'})
        self.assertEqual(r.status_code, 200)

    def test_kalendar_obsahuje_datum_odkaz(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse('kalendar'))
        self.assertContains(r, 'kalendar/nova')
        self.assertContains(r, 'datum=')

    def test_imap_vypadek_prehled(self):
        self.client.force_login(self.user)
        with patch('jadro.mail_prehled.overview_unseen', side_effect=Exception('down')):
            self.assertEqual(self.client.get(reverse('prehled')).status_code, 200)
