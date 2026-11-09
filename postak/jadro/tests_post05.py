from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from jadro.mail_sanitize import sanitize_html
from jadro.models import PoznamkaKoncept

MAIL_KEY = '5UJw-fkaQCvOYE6rjCyROlCttrakyH3-D8Qieby3Mvc='


@override_settings(POSTAK_PREFIX='', POSTAK_MAIL_ENCRYPTION_KEY=MAIL_KEY)
class Post05Tests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user('admin', password='x', is_superuser=True)
        self.eva = User.objects.create_user('eva', password='x')
        self.p1 = PoznamkaKoncept.objects.create(
            vlastnik=self.eva,
            nazev='Eva 1',
            poradi=2,
            obsah_html='<p>text eva</p>',
        )
        self.p2 = PoznamkaKoncept.objects.create(
            vlastnik=self.admin,
            nazev='Admin 1',
            poradi=1,
            obsah_html='<p>admin</p>',
        )

    def test_uzivatel_vidi_jen_vlastni(self):
        self.client.force_login(self.eva)
        resp = self.client.get(reverse('poznamky'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Eva 1')
        self.assertNotContains(resp, 'Admin 1')

    def test_cizi_zaznam_403(self):
        self.client.force_login(self.eva)
        self.assertEqual(self.client.get(reverse('poznamka_detail', args=[self.p2.pk])).status_code, 403)

    def test_admin_nevidi_cizi_v_seznamu(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse('poznamky'))
        self.assertContains(resp, 'Admin 1')
        self.assertNotContains(resp, 'Eva 1')

    def test_vytvoreni_sanitizuje_html(self):
        self.client.force_login(self.eva)
        url = reverse('poznamka_nova')
        self.client.post(url, {
            'nazev': 'Nová',
            'poradi': 5,
            'obsah_html': '<p>ok</p><script>bad()</script>',
        })
        poz = PoznamkaKoncept.objects.get(vlastnik=self.eva, nazev='Nová')
        self.assertIn('ok', poz.obsah_html)
        self.assertNotIn('script', poz.obsah_html.lower())
        self.assertEqual(poz.obsah_html, sanitize_html('<p>ok</p><script>bad()</script>'))

    def test_uprava_a_mazani(self):
        self.client.force_login(self.eva)
        detail = reverse('poznamka_detail', args=[self.p1.pk])
        self.client.post(detail, {
            'nazev': 'Přejmenováno',
            'poradi': 0,
            'obsah_html': '<p><strong>tučné</strong></p>',
        })
        self.p1.refresh_from_db()
        self.assertEqual(self.p1.nazev, 'Přejmenováno')
        self.assertIn('<strong>', self.p1.obsah_html)
        self.client.post(reverse('poznamka_smazat', args=[self.p1.pk]))
        self.assertFalse(PoznamkaKoncept.objects.filter(pk=self.p1.pk).exists())

    def test_razeni_podle_nazvu(self):
        PoznamkaKoncept.objects.create(vlastnik=self.eva, nazev='Aaa', poradi=9)
        self.client.force_login(self.eva)
        resp = self.client.get(reverse('poznamky'), {'razeni': 'nazev'})
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode()
        self.assertLess(body.index('Aaa'), body.index('Eva 1'))
