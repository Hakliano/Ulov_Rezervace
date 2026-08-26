"""FLOW platba QR — bez e-mailu zákazníka jen zobrazí kód na obrazovce."""

from datetime import timedelta
from unittest.mock import patch

from django.test import Client, TestCase
from django.utils import timezone

from flow.models import FlowUser
from rezervace.models import Rezervace, Zamestnanec
from salons.models import Salon


class FlowPlatbaQrBezEmailuTests(TestCase):
    def setUp(self):
        self.salon = Salon.objects.create(name='Salon QR')
        self.owner = Zamestnanec.objects.create(
            salon=self.salon,
            jmeno='Owner',
            role=Zamestnanec.ROLE_MAJITEL,
            prihlasovaci_jmeno='owner-qr@test.local',
            aktivni=True,
            zobrazit_na_webu=False,
        )
        self.owner.set_password('Heslo1234')
        self.owner.save(update_fields=['password_hash'])
        self.flow_owner = FlowUser.objects.create(
            salon=self.salon,
            zamestnanec=self.owner,
            email='owner-qr@test.local',
            aktivni=True,
        )
        self.flow_owner.password_hash = self.owner.password_hash
        self.flow_owner.save(update_fields=['password_hash'])
        self.client = Client()

    def _login(self):
        r = self.client.post(
            '/api/flow/prihlaseni/',
            data={'email': 'owner-qr@test.local', 'password': 'Heslo1234'},
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 200)
        return r.json()['token']

    def _rezervace(self, **extra):
        now = timezone.now()
        data = {
            'salon': self.salon,
            'zamestnanec': self.owner,
            'zacatek': now,
            'konec': now + timedelta(hours=1),
            'stav': 'potvrzeno',
            'jmeno_host': 'Bez mailu',
            'email_host': '',
        }
        data.update(extra)
        return Rezervace.objects.create(**data)

    def test_qr_bez_emailu_nezasilá_mail(self):
        token = self._login()
        rez = self._rezervace()
        with patch('rezervace.services.notifikace_email.email_platba_qr') as send:
            r = self.client.post(
                f'/api/flow/rezervace/{rez.id}/platba/',
                data={
                    'castka': '150',
                    'ucet': '123456789/0300',
                    'variabilni_symbol': str(rez.id),
                },
                content_type='application/json',
                HTTP_X_FLOW_TOKEN=token,
            )
        self.assertEqual(r.status_code, 200, r.content)
        body = r.json()
        self.assertTrue(body['ok'])
        self.assertFalse(body['email_odeslan'])
        self.assertTrue(body['qr_png_base64'])
        self.assertIn('ukažte ho zákazníkovi', body['message'])
        send.assert_not_called()

    def test_zaloha_bez_emailu_zapise_vyzadano(self):
        token = self._login()
        rez = self._rezervace()
        with patch('rezervace.services.notifikace_email.email_platba_qr') as send:
            r = self.client.post(
                f'/api/flow/rezervace/{rez.id}/platba/',
                data={
                    'castka': '200',
                    'ucet': '123456789/0300',
                    'variabilni_symbol': str(rez.id),
                    'zaloha': True,
                },
                content_type='application/json',
                HTTP_X_FLOW_TOKEN=token,
            )
        self.assertEqual(r.status_code, 200, r.content)
        self.assertFalse(r.json()['email_odeslan'])
        send.assert_not_called()
        rez.refresh_from_db()
        self.assertIsNotNone(rez.zaloha_vyzadana_at)
        self.assertEqual(rez.zaloha_castka, 200)
