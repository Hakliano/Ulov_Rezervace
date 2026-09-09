"""SMTP heslo v DB musí být šifrované; odesílání pořád dostane plaintext."""

from django.test import TestCase, override_settings
from django.test import Client

from rezervace.models import RezervacniNastaveni
from rezervace.services.emails import get_email_config
from rezervace.services.smtp_secrets import (
    SMTP_SECRET_PREFIX,
    decrypt_smtp_secret,
    encrypt_smtp_secret,
    is_encrypted_smtp_secret,
)
from salons.models import Salon


PLAIN = 'SmtpSecretP03Unique!'


class SmtpSecretAtRestTests(TestCase):
    def setUp(self):
        self.salon = Salon.objects.create(
            name='Salon P03 SMTP',
            email='salon.p03@example.test',
        )
        self.nastaveni = RezervacniNastaveni.objects.create(
            salon=self.salon,
            smtp_host='smtp.example.test',
            smtp_port=465,
            smtp_use_ssl=True,
            smtp_user='smtp.p03@example.test',
            smtp_password=PLAIN,
        )

    def test_save_encrypts_password_in_database(self):
        self.nastaveni.refresh_from_db()
        stored = self.nastaveni.smtp_password
        self.assertTrue(is_encrypted_smtp_secret(stored))
        self.assertNotEqual(stored, PLAIN)
        self.assertNotIn(PLAIN, stored)
        self.assertEqual(decrypt_smtp_secret(stored), PLAIN)
        self.assertEqual(self.nastaveni.smtp_password_plain(), PLAIN)

    def test_get_email_config_returns_plaintext_for_sending(self):
        cfg = get_email_config(self.salon)
        self.assertTrue(cfg['smtp_ready'])
        self.assertEqual(cfg['password'], PLAIN)
        self.assertEqual(cfg['user'], 'smtp.p03@example.test')

    def test_legacy_plaintext_is_still_readable(self):
        RezervacniNastaveni.objects.filter(pk=self.nastaveni.pk).update(
            smtp_password='LegacyPlainP03',
        )
        self.nastaveni.refresh_from_db()
        self.assertFalse(is_encrypted_smtp_secret(self.nastaveni.smtp_password))
        self.assertEqual(get_email_config(self.salon)['password'], 'LegacyPlainP03')
        self.nastaveni.save(update_fields=['smtp_password'])
        self.nastaveni.refresh_from_db()
        self.assertTrue(is_encrypted_smtp_secret(self.nastaveni.smtp_password))
        self.assertEqual(self.nastaveni.smtp_password_plain(), 'LegacyPlainP03')

    def test_encrypt_is_idempotent(self):
        once = encrypt_smtp_secret(PLAIN)
        twice = encrypt_smtp_secret(once)
        self.assertEqual(once, twice)
        self.assertEqual(decrypt_smtp_secret(twice), PLAIN)

    def test_admin_email_get_never_returns_password(self):
        from datetime import timedelta

        from django.utils import timezone

        from rezervace.models import Zamestnanec, ZamestnanecSession

        owner = Zamestnanec.objects.create(
            salon=self.salon,
            jmeno='Majitel P03',
            role=Zamestnanec.ROLE_MAJITEL,
            prihlasovaci_jmeno='owner.p03@example.test',
            aktivni=True,
        )
        owner.set_password('Majitelka123x')
        owner.save()
        session = ZamestnanecSession.objects.create(
            zamestnanec=owner,
            expirace=timezone.now() + timedelta(days=1),
        )
        client = Client()
        res = client.get(
            f'/api/salon/{self.salon.id}/admin/email/',
            secure=True,
            HTTP_X_STAFF_TOKEN=str(session.token),
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertNotIn('smtp_password', data)
        self.assertTrue(data.get('smtp_password_nastaveno'))
        raw = res.content.decode()
        self.assertNotIn(PLAIN, raw)
        self.assertNotIn(SMTP_SECRET_PREFIX, raw)


class SmtpSecretKeyIsolationTests(TestCase):
    def test_wrong_key_does_not_return_plaintext(self):
        token = encrypt_smtp_secret(PLAIN)
        with override_settings(SMTP_ENCRYPTION_KEY='jiny-klic-p03-xyz'):
            self.assertEqual(decrypt_smtp_secret(token), '')
