"""I7 — aktivace FLOW majitele (Přejít do FLOW)."""

from django.test import Client, TestCase

from flow.models import FlowUser
from rezervace.models import Zamestnanec
from rezervace.services.staff_auth import ensure_owner_flow_user, owner_flow_stav
from salons.models import Salon


class EnsureOwnerFlowUserTests(TestCase):
    def setUp(self):
        self.salon = Salon.objects.create(name='Salon I7', email='kontakt@i7.test')
        self.owner = Zamestnanec.objects.create(
            salon=self.salon,
            jmeno='Majitelka',
            role=Zamestnanec.ROLE_MAJITEL,
            prihlasovaci_jmeno='owner-i7@test.local',
            aktivni=True,
            zobrazit_na_webu=False,
        )
        self.owner.set_password('Heslo1234')
        self.owner.save(update_fields=['password_hash'])
        self.client = Client()

    def _login_staff(self):
        r = self.client.post(
            f'/api/salon/{self.salon.id}/rezervace/staff/prihlaseni/',
            data={'email': 'owner-i7@test.local', 'password': 'Heslo1234'},
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()['token']

    def test_ensure_creates_and_is_idempotent(self):
        self.assertFalse(owner_flow_stav(self.salon)['aktivni'])
        user, created = ensure_owner_flow_user(self.salon)
        self.assertTrue(created)
        self.assertEqual(user.email, 'owner-i7@test.local')
        self.assertEqual(user.password_hash, self.owner.password_hash)
        self.assertTrue(owner_flow_stav(self.salon)['aktivni'])

        user2, created2 = ensure_owner_flow_user(self.salon)
        self.assertFalse(created2)
        self.assertEqual(user2.id, user.id)

    def test_aktivace_api(self):
        token = self._login_staff()
        r = self.client.get(
            f'/api/salon/{self.salon.id}/flow/aktivace/',
            HTTP_X_STAFF_TOKEN=token,
        )
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json()['aktivni'])

        r2 = self.client.post(
            f'/api/salon/{self.salon.id}/flow/aktivace/',
            data={},
            content_type='application/json',
            HTTP_X_STAFF_TOKEN=token,
        )
        self.assertEqual(r2.status_code, 201)
        self.assertTrue(r2.json()['aktivni'])
        self.assertTrue(r2.json()['vytvoreno'])
        self.assertTrue(
            FlowUser.objects.filter(zamestnanec=self.owner, email='owner-i7@test.local').exists()
        )

        r3 = self.client.post(
            f'/api/salon/{self.salon.id}/flow/aktivace/',
            data={},
            content_type='application/json',
            HTTP_X_STAFF_TOKEN=token,
        )
        self.assertEqual(r3.status_code, 200)
        self.assertFalse(r3.json()['vytvoreno'])

    def test_requires_email_when_login_not_email(self):
        self.owner.prihlasovaci_jmeno = 'majitelka'
        self.owner.save(update_fields=['prihlasovaci_jmeno'])
        self.salon.email = ''
        self.salon.save(update_fields=['email'])
        with self.assertRaises(ValueError):
            ensure_owner_flow_user(self.salon)
        user, created = ensure_owner_flow_user(self.salon, email='nova@i7.test')
        self.assertTrue(created)
        self.assertEqual(user.email, 'nova@i7.test')
        self.owner.refresh_from_db()
        self.assertEqual(self.owner.prihlasovaci_jmeno, 'nova@i7.test')
