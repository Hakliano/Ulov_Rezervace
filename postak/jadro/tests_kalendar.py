from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from jadro.kalendar_models import KalendarUdalost
from jadro.klienti_constants import PROJEKT_HYA, PROJEKT_MODERNIK
from jadro.klienti_models import KlientHya, KlientModernik

MAIL_KEY = '5UJw-fkaQCvOYE6rjCyROlCttrakyH3-D8Qieby3Mvc='


def _dt(hour=10):
    loc = timezone.localtime()
    return loc.replace(hour=hour, minute=0, second=0, microsecond=0)


@override_settings(POSTAK_PREFIX='', POSTAK_MAIL_ENCRYPTION_KEY=MAIL_KEY)
class KalendarTests(TestCase):
    def setUp(self):
        self.a = User.objects.create_user('eva', password='x')
        self.b = User.objects.create_user('bob', password='x')
        self.su = User.objects.create_superuser('su', password='x')

    def _udalost(self, user, **kw):
        z = _dt()
        defaults = dict(nazev='Test', zacatek=z, konec=z + timedelta(hours=1), typ=KalendarUdalost.TYP_SCHUZKA, prirazeny=user, vytvoril=user)
        defaults.update(kw)
        return KalendarUdalost.objects.create(**defaults)

    def test_crud_vlastni(self):
        self.client.force_login(self.a)
        self.assertEqual(self.client.get(reverse('kalendar')).status_code, 200)
        self.assertContains(self.client.get(reverse('kalendar')), 'Měsíc')
        u = self._udalost(self.a)
        r = self.client.post(reverse('kalendar_upravit', args=[u.pk]), {
            'nazev': 'Schůzka upravená',
            'typ': 'schuzka',
            'zacatek': u.zacatek.strftime('%Y-%m-%dT%H:%M'),
            'konec': u.konec.strftime('%Y-%m-%dT%H:%M'),
            'prirazeny': self.a.pk,
            'klient': '',
            'popis': '',
        })
        self.assertEqual(r.status_code, 302)
        self.assertEqual(KalendarUdalost.objects.get(pk=u.pk).nazev, 'Schůzka upravená')
        self.client.post(reverse('kalendar_smazat', args=[u.pk]))
        self.assertFalse(KalendarUdalost.objects.filter(pk=u.pk).exists())

    def test_bob_nesmí_upravit_evu(self):
        u = self._udalost(self.a)
        self.client.force_login(self.b)
        self.assertEqual(self.client.get(reverse('kalendar_upravit', args=[u.pk])).status_code, 403)

    def test_superuser_muze(self):
        u = self._udalost(self.a)
        self.client.force_login(self.su)
        self.assertEqual(self.client.get(reverse('kalendar_upravit', args=[u.pk])).status_code, 200)

    def test_klient_modernik_hya(self):
        km = KlientModernik.objects.create(remote_id=1, jmeno='M', email='m@t.cz', stav='x', stav_label='X', remote_upraveno=timezone.now())
        kh = KlientHya.objects.create(remote_id=1, jmeno='H', email='h@t.cz', stav='y', stav_label='Y', remote_upraveno=timezone.now())
        self.client.force_login(self.a)
        z = _dt()
        r = self.client.post(reverse('kalendar_nova'), {
            'nazev': 's Mod',
            'typ': 'schuzka',
            'zacatek': z.strftime('%Y-%m-%dT%H:%M'),
            'konec': (z + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M'),
            'prirazeny': self.a.pk,
            'klient': f'{PROJEKT_MODERNIK}:{km.pk}',
        })
        self.assertEqual(r.status_code, 302)
        ev = KalendarUdalost.objects.get(nazev='s Mod')
        self.assertEqual(ev.klient_modernik_id, km.pk)
        r2 = self.client.post(reverse('kalendar_nova'), {
            'nazev': 's Hya',
            'typ': 'ukol',
            'zacatek': z.strftime('%Y-%m-%dT%H:%M'),
            'konec': (z + timedelta(hours=2)).strftime('%Y-%m-%dT%H:%M'),
            'prirazeny': self.a.pk,
            'klient': f'{PROJEKT_HYA}:{kh.pk}',
        })
        self.assertEqual(r2.status_code, 302)
        self.assertTrue(KalendarUdalost.objects.filter(klient_hya=kh).exists())

    def test_ukol_hotovo(self):
        u = self._udalost(self.a, typ=KalendarUdalost.TYP_UKOL)
        self.client.force_login(self.a)
        self.client.post(reverse('kalendar_hotovo', args=[u.pk]), {'hotovo': '1'})
        self.assertTrue(KalendarUdalost.objects.get(pk=u.pk).hotovo)

    def test_prehled(self):
        self._udalost(self.a, typ=KalendarUdalost.TYP_SCHUZKA, nazev='Dnes')
        self.client.force_login(self.a)
        self.assertContains(self.client.get(reverse('prehled')), 'Dnešní program')

    def test_zobrazeni(self):
        self.client.force_login(self.a)
        self.assertContains(self.client.get(reverse('kalendar') + '?z=tyden'), 'Týden')
        self.assertEqual(self.client.get(reverse('kalendar') + '?z=seznam').status_code, 200)
