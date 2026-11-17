from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from jadro.models import Profil
from jadro.user_activity import (
    AKTIVITA_THROTTLE_SEC,
    HISTORIE_PRIHLASENI_DNI,
    ZapisPosledniAktivityMiddleware,
    historie_prihlaseni,
    smaz_stara_prihlaseni,
    uzivatel_je_online,
    zapis_posledni_aktivitu,
)
from jadro.user_credentials_models import PrihlaseniHistorie


class UserActivityTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user('admin', password='x', is_superuser=True)
        self.user = User.objects.create_user('eva', password='x')
        self.client.login(username='admin', password='x')

    def test_uzivatele_vyzaduje_superusera(self):
        self.client.logout()
        self.client.login(username='eva', password='x')
        self.assertEqual(self.client.get(reverse('uzivatele')).status_code, 403)

    def test_prihlaseni_vytvori_historii(self):
        self.client.logout()
        self.assertEqual(PrihlaseniHistorie.objects.filter(uzivatel=self.user).count(), 0)
        self.client.login(username='eva', password='x')
        self.assertEqual(PrihlaseniHistorie.objects.filter(uzivatel=self.user).count(), 1)
        self.client.logout()
        self.client.login(username='admin', password='x')
        self.assertContains(self.client.get(reverse('uzivatele')), 'Posledn')

    def test_stara_prihlaseni_se_smazou(self):
        staré = timezone.now() - timedelta(days=HISTORIE_PRIHLASENI_DNI + 1)
        záznam = PrihlaseniHistorie.objects.create(uzivatel=self.user)
        PrihlaseniHistorie.objects.filter(pk=záznam.pk).update(vytvoreno=staré)
        smaz_stara_prihlaseni()
        self.assertFalse(PrihlaseniHistorie.objects.filter(pk=záznam.pk).exists())

    def test_historie_pouze_30_dni(self):
        staré = timezone.now() - timedelta(days=HISTORIE_PRIHLASENI_DNI + 2)
        nové = PrihlaseniHistorie.objects.create(uzivatel=self.user)
        old = PrihlaseniHistorie.objects.create(uzivatel=self.user)
        PrihlaseniHistorie.objects.filter(pk=old.pk).update(vytvoreno=staré)
        qs = historie_prihlaseni(self.user)
        self.assertIn(nové.pk, list(qs.values_list('pk', flat=True)))
        self.assertNotIn(old.pk, list(qs.values_list('pk', flat=True)))

    def test_aktivita_throttle(self):
        zapis_posledni_aktivitu(self.user)
        profil = Profil.objects.get(user=self.user)
        prvni = profil.posledni_aktivita
        self.assertIsNotNone(prvni)
        zapis_posledni_aktivitu(self.user)
        profil.refresh_from_db()
        self.assertEqual(profil.posledni_aktivita, prvni)
        with patch('jadro.user_activity.timezone.now', return_value=prvni + timedelta(seconds=AKTIVITA_THROTTLE_SEC + 1)):
            zapis_posledni_aktivitu(self.user)
        profil.refresh_from_db()
        self.assertGreater(profil.posledni_aktivita, prvni)

    def test_online_5_minut(self):
        profil, _ = Profil.objects.get_or_create(user=self.user)
        profil.posledni_aktivita = timezone.now() - timedelta(minutes=3)
        profil.save(update_fields=['posledni_aktivita'])
        self.assertTrue(uzivatel_je_online(profil))
        profil.posledni_aktivita = timezone.now() - timedelta(minutes=6)
        profil.save(update_fields=['posledni_aktivita'])
        self.assertFalse(uzivatel_je_online(profil))

    def test_middleware_preskoci_static(self):
        rf = RequestFactory()
        request = rf.get('/postak/static/postak.css')
        request.user = self.user
        mw = ZapisPosledniAktivityMiddleware(lambda r: 'ok')
        mw(request)
        self.assertFalse(Profil.objects.filter(user=self.user, posledni_aktivita__isnull=False).exists())

    def test_detail_zobrazi_historii(self):
        PrihlaseniHistorie.objects.create(uzivatel=self.user)
        response = self.client.get(reverse('uzivatel_detail', args=[self.user.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Historie přihlášení')