"""I1 — sdílená identita ownera (web-admin + FLOW), login jen e-mailem."""

from django.test import TestCase, Client

from flow.auth import prihlasit_flow, odhlasit_flow, flow_user_do_dict
from flow.models import FlowUser
from rezervace.models import Zamestnanec
from rezervace.services.staff_auth import (
    staff_do_dict,
    zmen_sdilene_heslo_owner,
)
from salons.models import Salon


class OwnerSharedIdentityTests(TestCase):
    def setUp(self):
        self.salon = Salon.objects.create(name='Test Salon I1')
        self.owner = Zamestnanec.objects.create(
            salon=self.salon,
            jmeno='Majitel Test',
            role=Zamestnanec.ROLE_MAJITEL,
            prihlasovaci_jmeno='owner@test.local',
            aktivni=True,
            zobrazit_na_webu=False,
        )
        self.owner.set_password('majitelka123')
        self.owner.save(update_fields=['password_hash'])
        self.flow = FlowUser.objects.create(
            salon=self.salon,
            zamestnanec=self.owner,
            email='owner@test.local',
            visible_overview=True,
            aktivni=True,
        )
        self.flow.set_password('stare-flow-heslo9')
        self.flow.save(update_fields=['password_hash'])

    def test_staff_dict_aliases(self):
        d = staff_do_dict(self.owner)
        self.assertTrue(d['je_owner'])
        self.assertTrue(d['je_majitel'])
        self.assertEqual(d['role_ui'], 'owner')
        self.assertEqual(d['email'], 'owner@test.local')

    def test_flow_login_uses_owner_staff_password(self):
        session, user = prihlasit_flow('owner@test.local', 'majitelka123')
        self.assertEqual(user.id, self.flow.id)
        self.assertTrue(flow_user_do_dict(user)['zamestnanec']['je_owner'])
        odhlasit_flow(str(session.token))

    def test_flow_rejects_username_login(self):
        with self.assertRaises(ValueError):
            prihlasit_flow('majitelka', 'majitelka123')

    def test_web_login_by_email(self):
        client = Client()
        login = client.post(
            f'/api/salon/{self.salon.id}/rezervace/staff/prihlaseni/',
            data={'email': 'owner@test.local', 'password': 'majitelka123'},
            content_type='application/json',
        )
        self.assertEqual(login.status_code, 200)
        self.assertTrue(login.json()['staff']['je_owner'])

    def test_web_rejects_username_login(self):
        client = Client()
        login = client.post(
            f'/api/salon/{self.salon.id}/rezervace/staff/prihlaseni/',
            data={'email': 'majitelka', 'password': 'majitelka123'},
            content_type='application/json',
        )
        self.assertEqual(login.status_code, 400)

    def test_zmena_hesla_syncs_flow(self):
        zmen_sdilene_heslo_owner(self.owner, 'majitelka123', 'NoveHeslo12')
        self.owner.refresh_from_db()
        self.flow.refresh_from_db()
        self.assertTrue(self.owner.check_password('NoveHeslo12'))
        self.assertTrue(self.flow.check_password('NoveHeslo12'))
        session, _ = prihlasit_flow('owner@test.local', 'NoveHeslo12')
        odhlasit_flow(str(session.token))

    def test_api_zmena_hesla_and_flow_blocks_owner_self_change(self):
        client = Client()
        login = client.post(
            f'/api/salon/{self.salon.id}/rezervace/staff/prihlaseni/',
            data={'email': 'owner@test.local', 'password': 'majitelka123'},
            content_type='application/json',
        )
        self.assertEqual(login.status_code, 200)
        token = login.json()['token']
        change = client.post(
            f'/api/salon/{self.salon.id}/rezervace/staff/zmena-hesla/',
            data={'current_password': 'majitelka123', 'new_password': 'NoveHeslo12'},
            content_type='application/json',
            HTTP_X_STAFF_TOKEN=token,
        )
        self.assertEqual(change.status_code, 200)

        flow_login = client.post(
            '/api/flow/prihlaseni/',
            data={'email': 'owner@test.local', 'password': 'NoveHeslo12'},
            content_type='application/json',
        )
        self.assertEqual(flow_login.status_code, 200)
        flow_token = flow_login.json()['token']
        blocked = client.post(
            '/api/flow/zmena-hesla/',
            data={'current_password': 'NoveHeslo12', 'new_password': 'JineHeslo99'},
            content_type='application/json',
            HTTP_X_FLOW_TOKEN=flow_token,
        )
        self.assertEqual(blocked.status_code, 400)
        self.assertIn('webové administraci', blocked.json()['detail'])

    def test_owner_emails_must_be_unique_across_salons(self):
        from rezervace.services.staff_auth import sync_owner_login_email

        salon2 = Salon.objects.create(name='Test Salon I1 B')
        owner2 = Zamestnanec.objects.create(
            salon=salon2,
            jmeno='Majitel 2',
            role=Zamestnanec.ROLE_MAJITEL,
            prihlasovaci_jmeno='owner2@test.local',
            aktivni=True,
            zobrazit_na_webu=False,
        )
        with self.assertRaises(ValueError):
            sync_owner_login_email(owner2, 'owner@test.local')
