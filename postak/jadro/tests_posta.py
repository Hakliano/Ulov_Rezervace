from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from jadro.mail_secrets import encrypt_secret
from jadro.mail_sanitize import sanitize_html
from jadro.models import EmailSchranka

MAIL_KEY = '5UJw-fkaQCvOYE6rjCyROlCttrakyH3-D8Qieby3Mvc='
HESLO = 'box-heslo-1'


@override_settings(POSTAK_PREFIX='', POSTAK_MAIL_ENCRYPTION_KEY=MAIL_KEY)
class PostaTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user('admin', password='x')
        self.admin.is_superuser = True
        self.admin.save(update_fields=['is_superuser'])
        self.user = User.objects.create_user('eva', password='x')
        self.box = EmailSchranka.objects.create(
            email='a@modernik.cz',
            projekt=EmailSchranka.PROJEKT_MODERNIK,
            prihlasovaci_jmeno='a@modernik.cz',
            heslo_sifra=encrypt_secret(HESLO),
        )
        self.box2 = EmailSchranka.objects.create(
            email='b@hereyouare.cz',
            projekt=EmailSchranka.PROJEKT_HYA,
            prihlasovaci_jmeno='b@hereyouare.cz',
            heslo_sifra=encrypt_secret(HESLO),
        )

    def test_html_sanitize_odstrani_skrpty(self):
        out = sanitize_html('<p>ahoj</p><script>alert(1)</script><img src="http://evil.test/x.png">')
        self.assertNotIn('script', out)
        self.assertIn('[obrázek]', out)

    def test_stripe_html_je_citelne(self):
        from jadro.mail_sanitize import display_bodies, prepare_email_html
        raw = (
            '<html><head><style>body{color:#333}</style></head><body>'
            '<p>Platba přijata</p><table><tr><td>999 Kč</td></tr></table></body></html>'
        )
        prepared = prepare_email_html(raw)
        self.assertNotIn('@media', prepared.lower())
        text, html = display_bodies('', raw)
        self.assertIn('Platba', text)
        self.assertTrue(html)
        self.assertNotIn('body{color', html)

    @patch('jadro.posta_views.list_page')
    @patch('jadro.posta_views.list_folders', return_value=[{'name': 'INBOX', 'label': 'Doručená'}])
    def test_user_vidi_jen_prirazene(self, _folders, list_page):
        list_page.return_value = {
            'folder': 'INBOX',
            'uidvalidity': '1',
            'items': [{'uid': 9, 'from_name': 'Jan', 'from_email': 'j@x.cz', 'to': '', 'subject': 'Test', 'date': '', 'unread': True}],
            'total': 1,
            'page': 1,
            'pages': 1,
            'per_page': 25,
        }
        self.box.uzivatele.add(self.user)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('posta_seznam', args=[self.box2.pk])).status_code, 403)
        ok = self.client.get(reverse('posta_seznam', args=[self.box.pk]))
        self.assertEqual(ok.status_code, 200)
        self.assertContains(ok, 'Test')
        self.assertEqual(self.client.get(reverse('posta_zprava', args=[self.box2.pk, 1])).status_code, 403)

    @patch('jadro.posta_views.get_detail')
    @patch('jadro.posta_views.list_folders', return_value=[])
    def test_zprava_a_priloha(self, _folders, get_detail):
        get_detail.return_value = {
            'uid': 5,
            'uidvalidity': '99',
            'folder': 'INBOX',
            'subject': 'Předmět',
            'from': 'odesilatel@modernik.cz',
            'to': 'a@modernik.cz',
            'date': '1.1.2025',
            'unread': False,
            'body_text': 'Tělo',
            'body_html': '',
            'attachments': [{'part': 1, 'filename': 'doc.pdf', 'content_type': 'application/pdf', 'size': 3}],
        }
        self.client.force_login(self.admin)
        detail = self.client.get(reverse('posta_zprava', args=[self.box.pk, 5]))
        self.assertContains(detail, 'Předmět')
        with patch('jadro.posta_views.fetch_attachment', return_value=(b'pdf', 'doc.pdf', 'application/pdf')):
            file_resp = self.client.get(reverse('posta_priloha', args=[self.box.pk, 5, 1]))
            self.assertEqual(file_resp.status_code, 200)
            self.assertEqual(file_resp['Content-Type'], 'application/pdf')
