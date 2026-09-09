"""Veřejný GET /api/salon/<pk>/rezervace/info/ nesmí unikat interní údaje."""

import json

from django.test import Client, TestCase

from rezervace.models import RezervacniNastaveni, Zamestnanec, ZamestnanecSluzba
from salons.models import CenikPolozka, Salon


FORBIDDEN_KEYS = frozenset({
    'prihlasovaci_jmeno',
    'cislo_uctu',
    'role',
    'role_ui',
    'ma_prihlaseni',
    'je_majitel',
    'je_owner',
    'password_hash',
    'heslo',
    'email_smtp',
    'email_odesilatel',
    'email_jmeno_odesilatele',
    'smtp_host',
    'smtp_port',
    'smtp_user',
    'smtp_password',
    'smtp_use_ssl',
    'imap_host',
    'imap_port',
    'imap_user',
    'imap_password',
    'imap_use_ssl',
    'imap_enabled',
    'notifikace',
    'notifikace_placeholders',
    'notifikace_tagy',
    'nastaveni',
    'web_rezervace_url',
    'recenze_url',
    'platba_qr_text',
    'auto_potvrzeni',
    'potvrzeni_platnost_hodin',
    'storno_do_hodin',
    'interval_minut',
    'min_predstih_hodin',
    'max_predstih_mesicu',
    'gdpr_zasady_verze',
})

ALLOWED_TOP_LEVEL = frozenset({'salon', 'sluzby', 'zamestnanci', 'gdpr'})
ALLOWED_SALON = frozenset({'id', 'name', 'address', 'phone', 'email'})
ALLOWED_STAFF = frozenset({'id', 'jmeno', 'specializace', 'sluzby_ids'})
ALLOWED_SLUZBA = frozenset({'id', 'nazev', 'cena', 'delka_minut', 'rezerva_minut', 'poradi'})
ALLOWED_GDPR = frozenset({'zasady_verze', 'jazyk'})

STAFF_LOGIN = 'secret.login.p02@example.test'
STAFF_ACCOUNT = 'CZ6508000000192000145399'
SMTP_USER = 'smtp.secret.p02@example.test'
SMTP_PASSWORD = 'SmtpPassP02UniqueX9'
SMTP_HOST = 'smtp.secret-p02.example.test'
FROM_EMAIL = 'from.secret.p02@example.test'
FROM_NAME = 'SecretSenderP02'
IMAP_HOST = 'imap.secret-p02.example.test'


def _collect_keys(value):
    keys = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            keys.add(key)
            keys.update(_collect_keys(nested))
    elif isinstance(value, list):
        for item in value:
            keys.update(_collect_keys(item))
    return keys


class RezervaceInfoPublicLeakTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.salon = Salon.objects.create(
            name='Salon P02 Public',
            address='Testovací 1',
            phone='777000111',
            email='salon.public.p02@example.test',
        )
        self.nastaveni = RezervacniNastaveni.objects.create(
            salon=self.salon,
            interval_minut=15,
            min_predstih_hodin=2,
            email_odesilatel=FROM_EMAIL,
            email_jmeno_odesilatele=FROM_NAME,
            smtp_host=SMTP_HOST,
            smtp_port=465,
            smtp_user=SMTP_USER,
            smtp_password=SMTP_PASSWORD,
            imap_host=IMAP_HOST,
            imap_enabled=True,
            recenze_url='https://secret-reviews.example.test/p02',
            web_rezervace_url='https://secret-booking.example.test/p02',
            platba_qr_text='Tajny QR text P02',
            notifikace=[{
                'id': 'p02-secret-notif',
                'typ': 'potvrzeni',
                'predmet': 'Tajny predmet P02',
                'text': 'Tajny text notifikace P02',
                'aktivni': True,
            }],
        )
        self.sluzba = CenikPolozka.objects.create(
            salon=self.salon,
            nazev='Střih P02',
            cena=500,
            delka_minut=45,
            rezerva_minut=5,
            aktivni=True,
        )
        self.staff = Zamestnanec.objects.create(
            salon=self.salon,
            jmeno='Anna Veřejná',
            specializace='Střihy',
            popis='Interní popis, který na rezervaci nepatří',
            role=Zamestnanec.ROLE_ZAMESTNANEC,
            prihlasovaci_jmeno=STAFF_LOGIN,
            cislo_uctu=STAFF_ACCOUNT,
            aktivni=True,
            zobrazit_na_webu=True,
        )
        self.staff.set_password('StaffPassP02Unique')
        self.staff.save(update_fields=['password_hash'])
        ZamestnanecSluzba.objects.create(zamestnanec=self.staff, sluzba=self.sluzba)
        Zamestnanec.objects.create(
            salon=self.salon,
            jmeno='Majitelka Skrytá',
            role=Zamestnanec.ROLE_MAJITEL,
            prihlasovaci_jmeno='owner.secret.p02@example.test',
            aktivni=True,
        )
        self.url = f'/api/salon/{self.salon.id}/rezervace/info/'

    def _get_payload(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_anonymous_info_omits_forbidden_keys_even_if_serializer_grows(self):
        payload = self._get_payload()
        leaked = _collect_keys(payload) & FORBIDDEN_KEYS
        self.assertEqual(
            leaked,
            set(),
            'Veřejné /rezervace/info/ obsahuje zakázaná pole. '
            'Nepoužívejte admin serializer (ZamestnanecSerializer / '
            'RezervacniNastaveniSerializer) ani SMTP konfiguraci.',
        )
        self.assertEqual(set(payload), ALLOWED_TOP_LEVEL)
        self.assertEqual(set(payload['salon']), ALLOWED_SALON)
        self.assertEqual(set(payload['gdpr']), ALLOWED_GDPR)
        self.assertEqual(len(payload['zamestnanci']), 1)
        self.assertEqual(set(payload['zamestnanci'][0]), ALLOWED_STAFF)
        self.assertEqual(set(payload['sluzby'][0]), ALLOWED_SLUZBA)

    def test_anonymous_info_does_not_embed_internal_values(self):
        raw = json.dumps(self._get_payload(), ensure_ascii=False)
        for secret in (
            STAFF_LOGIN,
            STAFF_ACCOUNT,
            SMTP_USER,
            SMTP_PASSWORD,
            SMTP_HOST,
            FROM_EMAIL,
            FROM_NAME,
            IMAP_HOST,
            'Tajny QR text P02',
            'Tajny predmet P02',
            'Tajny text notifikace P02',
            'Interní popis, který na rezervaci nepatří',
            'Majitelka Skrytá',
            'owner.secret.p02@example.test',
            'https://secret-reviews.example.test/p02',
            'StaffPassP02Unique',
        ):
            self.assertNotIn(secret, raw)

    def test_anonymous_info_keeps_public_booking_fields(self):
        payload = self._get_payload()
        staff = payload['zamestnanci'][0]
        self.assertEqual(staff['id'], self.staff.id)
        self.assertEqual(staff['jmeno'], 'Anna Veřejná')
        self.assertEqual(staff['specializace'], 'Střihy')
        self.assertEqual(staff['sluzby_ids'], [self.sluzba.id])
        self.assertEqual(payload['salon']['name'], 'Salon P02 Public')
        self.assertEqual(payload['salon']['email'], 'salon.public.p02@example.test')
        self.assertEqual(payload['sluzby'][0]['nazev'], 'Střih P02')
        self.assertEqual(payload['gdpr']['zasady_verze'], self.nastaveni.gdpr_zasady_verze)
        self.assertEqual(payload['gdpr']['jazyk'], 'cs')
