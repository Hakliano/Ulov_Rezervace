"""SMTP heslo v DB musí být šifrované; odesílání pořád dostane plaintext v paměti."""

from django.test import Client, TestCase, override_settings
from django.core import mail

from rezervace.models import RezervacniNastaveni
from rezervace.services.emails import SmtpNotReady, get_email_config, _odeslat_pro_salon
from rezervace.services.smtp_secrets import (
    SMTP_SECRET_PREFIX,
    SmtpDecryptError,
    decrypt_smtp_secret,
    encrypt_smtp_secret,
    is_encrypted_smtp_secret,
)
from rezervace.tasks import task_email_test
from salons.models import Salon


PLAIN = 'SmtpSecretP03Unique!'
KEY_A = 'MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA='
KEY_B = 'AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8='
ULOV_FALLBACK_PASSWORD = 'UlovFallbackMustNotBeUsed'


@override_settings(
    SMTP_ENCRYPTION_KEY=KEY_A,
    SMTP_ENCRYPTION_PREVIOUS_KEYS=[],
    EMAIL_HOST='smtp.ulov-fallback.test',
    EMAIL_HOST_USER='ulov@fallback.test',
    EMAIL_HOST_PASSWORD=ULOV_FALLBACK_PASSWORD,
    EMAIL_PORT=465,
    EMAIL_USE_SSL=True,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
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
        self.assertEqual(cfg['zdroj'], 'admin')
        self.assertEqual(cfg['password'], PLAIN)
        self.assertEqual(cfg['user'], 'smtp.p03@example.test')

    def test_legacy_plaintext_is_ignored_no_ulov_fallback(self):
        RezervacniNastaveni.objects.filter(pk=self.nastaveni.pk).update(
            smtp_password='LegacyPlainP03',
        )
        self.nastaveni.refresh_from_db()
        cfg = get_email_config(self.salon)
        self.assertEqual(cfg['zdroj'], 'admin_incomplete')
        self.assertFalse(cfg['smtp_ready'])
        self.assertEqual(cfg['password'], '')
        self.assertNotEqual(cfg['password'], 'LegacyPlainP03')
        self.assertNotEqual(cfg['password'], ULOV_FALLBACK_PASSWORD)
        with self.assertRaises(SmtpNotReady) as caught:
            _odeslat_pro_salon(self.salon, 'x@test.local', 't', 'b')
        self.assertEqual(caught.exception.code, 'admin_incomplete')
        self.assertEqual(len(mail.outbox), 0)

    def test_missing_password_with_smtp_user_does_not_fallback(self):
        RezervacniNastaveni.objects.filter(pk=self.nastaveni.pk).update(smtp_password='')
        self.nastaveni.refresh_from_db()
        cfg = get_email_config(self.salon)
        self.assertEqual(cfg['zdroj'], 'admin_incomplete')
        self.assertFalse(cfg['smtp_ready'])
        self.assertEqual(cfg['password'], '')

    def test_never_configured_uses_ulov_fallback(self):
        RezervacniNastaveni.objects.filter(pk=self.nastaveni.pk).update(
            smtp_user='', smtp_password='',
        )
        self.nastaveni.refresh_from_db()
        cfg = get_email_config(self.salon)
        self.assertEqual(cfg['zdroj'], 'env')
        self.assertTrue(cfg['smtp_ready'])
        self.assertEqual(cfg['password'], ULOV_FALLBACK_PASSWORD)

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
        self.assertEqual(data.get('smtp_stav'), 'admin')
        raw = res.content.decode()
        self.assertNotIn(PLAIN, raw)
        self.assertNotIn(SMTP_SECRET_PREFIX, raw)

    def test_celery_task_only_takes_ids(self):
        names = set(task_email_test.run.__code__.co_varnames)
        self.assertIn('salon_id', task_email_test.run.__code__.co_varnames)
        self.assertNotIn('password', names)
        self.assertNotIn('smtp_password', names)


@override_settings(SMTP_ENCRYPTION_KEY=KEY_A, SMTP_ENCRYPTION_PREVIOUS_KEYS=[])
class SmtpSecretKeyIsolationTests(TestCase):
    def test_wrong_key_is_fail_closed_no_fallback(self):
        token = encrypt_smtp_secret(PLAIN)
        salon = Salon.objects.create(name='Salon decrypt error', email='d@test.local')
        RezervacniNastaveni.objects.create(
            salon=salon,
            smtp_user='own@test.local',
            smtp_password=token,
        )
        with override_settings(
            SMTP_ENCRYPTION_KEY=KEY_B,
            SMTP_ENCRYPTION_PREVIOUS_KEYS=[],
            EMAIL_HOST_PASSWORD=ULOV_FALLBACK_PASSWORD,
            EMAIL_HOST_USER='ulov@fallback.test',
        ):
            with self.assertRaises(SmtpDecryptError):
                decrypt_smtp_secret(token)
            cfg = get_email_config(salon)
            self.assertEqual(cfg['zdroj'], 'decrypt_error')
            self.assertFalse(cfg['smtp_ready'])
            self.assertEqual(cfg['password'], '')
            with self.assertRaises(SmtpNotReady) as caught:
                _odeslat_pro_salon(salon, 'x@test.local', 't', 'b')
            self.assertEqual(caught.exception.code, 'decrypt_error')

    def test_previous_key_still_decrypts(self):
        token = encrypt_smtp_secret(PLAIN)
        with override_settings(
            SMTP_ENCRYPTION_KEY=KEY_B,
            SMTP_ENCRYPTION_PREVIOUS_KEYS=[KEY_A],
        ):
            self.assertEqual(decrypt_smtp_secret(token), PLAIN)
