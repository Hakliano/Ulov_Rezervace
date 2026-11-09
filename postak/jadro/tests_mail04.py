from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from email import message_from_bytes

from jadro.mail_compose_body import quote_reply_html
from jadro.mail_send import build_message
from jadro.mail_secrets import encrypt_secret
from jadro.mail_sanitize import normalize_compose_body, sanitize_html
from jadro.models import EmailSchranka

MAIL_KEY = '5UJw-fkaQCvOYE6rjCyROlCttrakyH3-D8Qieby3Mvc='


@override_settings(POSTAK_PREFIX='', POSTAK_MAIL_ENCRYPTION_KEY=MAIL_KEY)
class Mail04Tests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user('admin', password='x', is_superuser=True)
        self.box = EmailSchranka.objects.create(
            email='a@modernik.cz',
            projekt=EmailSchranka.PROJEKT_MODERNIK,
            prihlasovaci_jmeno='a@modernik.cz',
            heslo_sifra=encrypt_secret('heslo'),
            podpis_html='<p>S pozdravem<br>Moderník</p>',
        )

    def test_normalize_compose_odstrani_nebezpeci(self):
        safe, plain = normalize_compose_body('<p>ahoj</p><script>x</script>')
        self.assertIn('ahoj', safe)
        self.assertNotIn('script', safe.lower())
        self.assertIn('ahoj', plain)

    def test_build_message_html_a_plain_alternativa(self):
        body = '<p><strong>Dobrý den</strong></p>'
        msg, _ = build_message(
            self.box,
            to='prijemce@test.cz',
            subject='Test',
            body=body,
        )
        raw = msg.as_bytes()
        parsed = message_from_bytes(raw)
        parts = [p for p in parsed.walk() if p.get_content_type() in ('text/plain', 'text/html')]
        self.assertEqual(len(parts), 2)
        html = next(p.get_payload(decode=True).decode() for p in parts if p.get_content_type() == 'text/html')
        self.assertIn('Dobrý den', html)
        self.assertIn('posta-podpis', html)
        self.assertNotIn('<script', html.lower())

    def test_podpis_se_nedava_dvakrat(self):
        podpis = sanitize_html(self.box.podpis_html)
        body = f'<p>Text</p><div class="posta-podpis">{podpis}</div>'
        msg, _ = build_message(self.box, to='x@test.cz', subject='Re', body=body)
        html_part = next(
            p.get_payload(decode=True).decode('utf-8')
            for p in msg.walk()
            if p.get_content_type() == 'text/html'
        )
        self.assertEqual(html_part.count('Moderník'), 1)
        self.assertEqual(html_part.count('posta-podpis'), 1)

    def test_citace_odpovedi_je_html_bez_suroveho_obsahu(self):
        q = quote_reply_html(author='Jan', body_text='Platba 999 Kč')
        self.assertIn('blockquote', q)
        self.assertIn('Platba', q)
        self.assertNotIn('<table', q)

    @patch('jadro.posta_views.refresh_folder', return_value={'folder': 'INBOX', 'uidvalidity': '42'})
    def test_sync_schranka_redirect(self, refresh):
        self.client.force_login(self.admin)
        url = reverse('posta_sync', args=[self.box.pk])
        resp = self.client.post(url, {'slozka': 'INBOX', 'stranka': '1', 'uv': '41'})
        self.assertEqual(resp.status_code, 302)
        refresh.assert_called_once()
        follow = self.client.get(resp['Location'])
        self.assertContains(follow, 'aktualizovaná')
