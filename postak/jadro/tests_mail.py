from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from jadro.mail_secrets import decrypt_secret, encrypt_secret
from jadro.mail_test import Vysledek
from jadro.models import EmailSchranka

HESLO = 'Schranka-heslo-9'
MAIL_KEY = '5UJw-fkaQCvOYE6rjCyROlCttrakyH3-D8Qieby3Mvc='


@override_settings(POSTAK_PREFIX='', POSTAK_MAIL_ENCRYPTION_KEY=MAIL_KEY)
class MailUctyTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user('admin', password='admin-pass')
        self.admin.is_superuser = True
        self.admin.save(update_fields=['is_superuser'])
        self.user = User.objects.create_user('eva', password='eva-pass')

    def test_heslo_je_sifrovane(self):
        raw = 'tajne-heslo'
        enc = encrypt_secret(raw)
        self.assertTrue(enc.startswith('enc:v1:'))
        self.assertEqual(decrypt_secret(enc), raw)
        self.assertNotIn(raw, enc)

    def test_superuser_prida_schranku(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('email_ucet_novy'), {
            'email': 'info@modernik.cz',
            'projekt': EmailSchranka.PROJEKT_MODERNIK,
            'prihlasovaci_jmeno': 'info@modernik.cz',
            'heslo': HESLO,
            'imap_host': 'imap.forpsi.com',
            'imap_port': 993,
            'imap_ssl': 'on',
            'smtp_host': 'smtp.forpsi.com',
            'smtp_port': 465,
            'smtp_ssl': 'on',
        })
        schranka = EmailSchranka.objects.get(email='info@modernik.cz')
        self.assertRedirects(response, reverse('email_ucet_detail', args=[schranka.pk]))
        self.assertEqual(decrypt_secret(schranka.heslo_sifra), HESLO)
        detail = self.client.get(reverse('email_ucet_detail', args=[schranka.pk]))
        self.assertNotContains(detail, HESLO)
        self.assertNotContains(detail, schranka.heslo_sifra)

    def test_user_nevidi_cizi_schranku(self):
        schranka = EmailSchranka.objects.create(
            email='box@hereyouare.cz',
            projekt=EmailSchranka.PROJEKT_HYA,
            prihlasovaci_jmeno='box@hereyouare.cz',
            heslo_sifra=encrypt_secret(HESLO),
        )
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('email_ucty')).status_code, 200)
        self.assertEqual(self.client.get(reverse('email_ucet_novy')).status_code, 403)
        self.assertEqual(self.client.get(reverse('email_ucet_detail', args=[schranka.pk])).status_code, 403)

        schranka.uzivatele.add(self.user)
        detail = self.client.get(reverse('email_ucet_detail', args=[schranka.pk]))
        self.assertEqual(detail.status_code, 200)
        self.assertNotContains(detail, 'heslo')
        self.assertNotContains(detail, HESLO)
        self.assertEqual(
            self.client.post(reverse('email_ucet_test', args=[schranka.pk])).status_code,
            403,
        )

    @patch('jadro.mail_views.test_smtp', return_value=Vysledek(True, 'SMTP OK'))
    @patch('jadro.mail_views.test_imap', return_value=Vysledek(True, 'IMAP OK'))
    def test_test_pripojeni_a_pristup(self, _imap, _smtp):
        schranka = EmailSchranka.objects.create(
            email='sales@modernik.cz',
            projekt=EmailSchranka.PROJEKT_MODERNIK,
            prihlasovaci_jmeno='sales@modernik.cz',
            heslo_sifra=encrypt_secret(HESLO),
        )
        self.client.force_login(self.admin)
        response = self.client.post(reverse('email_ucet_test', args=[schranka.pk]))
        self.assertRedirects(response, reverse('email_ucet_detail', args=[schranka.pk]))
        schranka.refresh_from_db()
        self.assertEqual(schranka.test_stav, EmailSchranka.STAV_OK)

        self.client.post(reverse('email_ucet_detail', args=[schranka.pk]), {
            'akce': 'pristup',
            'uzivatele': [self.user.pk],
        })
        schranka.refresh_from_db()
        self.assertEqual(list(schranka.uzivatele.values_list('username', flat=True)), ['eva'])

        self.client.force_login(self.user)
        seznam = self.client.get(reverse('email_ucty'))
        self.assertContains(seznam, 'sales@modernik.cz')
