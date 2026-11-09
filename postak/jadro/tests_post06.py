from io import BytesIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from jadro.mail_secrets import encrypt_secret
from jadro.models import EmailKoncept, EmailSchranka, PoznamkaKoncept

MAIL_KEY = '5UJw-fkaQCvOYE6rjCyROlCttrakyH3-D8Qieby3Mvc='


@override_settings(POSTAK_PREFIX='', POSTAK_MAIL_ENCRYPTION_KEY=MAIL_KEY)
class Post06Tests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user('admin', password='x', is_superuser=True)
        self.eva = User.objects.create_user('eva', password='x')
        self.box = EmailSchranka.objects.create(
            email='a@modernik.cz',
            projekt=EmailSchranka.PROJEKT_MODERNIK,
            prihlasovaci_jmeno='a@modernik.cz',
            heslo_sifra=encrypt_secret('heslo'),
        )
        self.box.uzivatele.add(self.eva)
        self.poz = PoznamkaKoncept.objects.create(
            vlastnik=self.eva,
            nazev='Tajná',
            poradi=1,
            obsah_html='<p><strong>Text</strong></p>',
        )

    def test_poznamka_kopirovat_data_vlastnik(self):
        self.client.force_login(self.eva)
        resp = self.client.get(reverse('poznamka_kopirovat', args=[self.poz.pk]))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('<strong>', data['html'])

    def test_poznamka_kopirovat_cizi_403(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse('poznamka_kopirovat', args=[self.poz.pk])).status_code, 403)

    def test_ulozit_a_aktualizovat_koncept(self):
        self.client.force_login(self.eva)
        url = reverse('posta_napsat', args=[self.box.pk])
        r1 = self.client.post(url, {
            'akce': 'koncept',
            'komu': 'kam@modernik.cz',
            'predmet': 'První',
            'telo': '<p>jedna</p>',
        })
        self.assertEqual(r1.status_code, 302)
        kid = EmailKoncept.objects.get(vlastnik=self.eva).pk
        r2 = self.client.post(url, {
            'akce': 'koncept',
            'koncept_id': kid,
            'komu': 'kam@modernik.cz',
            'predmet': 'Druhá',
            'telo': '<p>dva</p>',
        })
        self.assertEqual(r2.status_code, 302)
        self.assertEqual(EmailKoncept.objects.filter(vlastnik=self.eva).count(), 1)
        k = EmailKoncept.objects.get(pk=kid)
        self.assertEqual(k.predmet, 'Druhá')

    @patch('jadro.posta_compose.send_message')
    def test_odeslani_smaze_koncept(self, send):
        send.return_value = 'msg-id'
        k = EmailKoncept.objects.create(
            vlastnik=self.eva,
            schranka=self.box,
            komu='x@test.cz',
            predmet='Odejde',
            telo_html='<p>ahoj</p>',
        )
        self.client.force_login(self.eva)
        session = self.client.session
        session['posta_otp'] = 'abc'
        session.save()
        url = reverse('posta_napsat', args=[self.box.pk])
        self.client.post(url, {
            'akce': 'odeslat',
            'otp': 'abc',
            'koncept_id': k.pk,
            'komu': 'x@test.cz',
            'predmet': 'Odejde',
            'telo': '<p>ahoj</p>',
        })
        send.assert_called_once()
        self.assertFalse(EmailKoncept.objects.filter(pk=k.pk).exists())

    @patch('jadro.posta_compose.send_message', side_effect=Exception('smtp'))
    def test_neuspech_odeslani_koncept_zustane(self, send):
        from jadro.mail_imap import MailError

        def boom(*a, **kw):
            raise MailError('smtp')

        send.side_effect = boom
        k = EmailKoncept.objects.create(
            vlastnik=self.eva,
            schranka=self.box,
            komu='x@test.cz',
            predmet='Zůstane',
            telo_html='<p>z</p>',
        )
        self.client.force_login(self.eva)
        session = self.client.session
        session['posta_otp'] = 'tok'
        session.save()
        self.client.post(reverse('posta_napsat', args=[self.box.pk]), {
            'akce': 'odeslat',
            'otp': 'tok',
            'koncept_id': k.pk,
            'komu': 'x@test.cz',
            'predmet': 'Zůstane',
            'telo': '<p>z</p>',
        })
        self.assertTrue(EmailKoncept.objects.filter(pk=k.pk).exists())

    def test_koncepty_jen_vlastnik(self):
        EmailKoncept.objects.create(vlastnik=self.eva, schranka=self.box, komu='a', predmet='Eva K')
        EmailKoncept.objects.create(vlastnik=self.admin, schranka=self.box, komu='b', predmet='Admin K')
        self.client.force_login(self.eva)
        resp = self.client.get(reverse('posta_koncepty'))
        self.assertContains(resp, 'Eva K')
        self.assertNotContains(resp, 'Admin K')

    def test_koncept_s_prilohou(self):
        self.client.force_login(self.eva)
        f = SimpleUploadedFile('doc.txt', b'hello', content_type='text/plain')
        url = reverse('posta_napsat', args=[self.box.pk])
        self.client.post(url, {
            'akce': 'koncept',
            'komu': 'kam@modernik.cz',
            'predmet': 'S přílohou',
            'telo': '<p>x</p>',
            'prilohy': f,
        })
        k = EmailKoncept.objects.get(vlastnik=self.eva)
        self.assertEqual(k.prilohy.count(), 1)
