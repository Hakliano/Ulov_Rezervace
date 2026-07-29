"""I4 — FLOW owner personál + staff rozvrh view-only."""

from django.test import TestCase, Client

from flow.models import FlowUser
from rezervace.models import Zamestnanec
from salons.models import Salon


class FlowOwnerPersonalTests(TestCase):
    def setUp(self):
        self.salon = Salon.objects.create(name='Salon I4')
        self.owner = Zamestnanec.objects.create(
            salon=self.salon,
            jmeno='Owner',
            role=Zamestnanec.ROLE_MAJITEL,
            prihlasovaci_jmeno='owner-i4@test.local',
            aktivni=True,
            zobrazit_na_webu=False,
        )
        self.owner.set_password('Heslo1234')
        self.owner.save(update_fields=['password_hash'])
        self.flow_owner = FlowUser.objects.create(
            salon=self.salon,
            zamestnanec=self.owner,
            email='owner-i4@test.local',
            aktivni=True,
            visible_overview=True,
        )
        self.flow_owner.password_hash = self.owner.password_hash
        self.flow_owner.save(update_fields=['password_hash'])

        self.staff = Zamestnanec.objects.create(
            salon=self.salon,
            jmeno='Staff',
            role=Zamestnanec.ROLE_ZAMESTNANEC,
            prihlasovaci_jmeno='staff-i4',
            aktivni=True,
            zobrazit_na_webu=True,
            cislo_uctu='',
        )
        self.flow_staff = FlowUser.objects.create(
            salon=self.salon,
            zamestnanec=self.staff,
            email='staff-i4@test.local',
            aktivni=True,
        )
        self.flow_staff.set_password('Staff1234')
        self.flow_staff.save(update_fields=['password_hash'])
        self.client = Client()

    def _login(self, email, password):
        r = self.client.post(
            '/api/flow/prihlaseni/',
            data={'email': email, 'password': password},
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 200)
        return r.json()['token']

    def test_owner_lists_and_updates_staff(self):
        token = self._login('owner-i4@test.local', 'Heslo1234')
        listing = self.client.get('/api/flow/owner/personal/', HTTP_X_FLOW_TOKEN=token)
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(len(listing.json()['zamestnanci']), 2)

        put = self.client.put(
            f'/api/flow/owner/personal/{self.staff.id}/',
            data={'cislo_uctu': '111222333/0100', 'jmeno': 'Staff Upraveny'},
            content_type='application/json',
            HTTP_X_FLOW_TOKEN=token,
        )
        self.assertEqual(put.status_code, 200)
        self.staff.refresh_from_db()
        self.assertEqual(self.staff.cislo_uctu, '111222333/0100')
        self.assertEqual(self.staff.jmeno, 'Staff Upraveny')

    def test_owner_can_block_flow_login_only(self):
        token = self._login('owner-i4@test.local', 'Heslo1234')
        patch = self.client.patch(
            f'/api/flow/owner/personal/{self.staff.id}/flow/patch/',
            data={'aktivni': False},
            content_type='application/json',
            HTTP_X_FLOW_TOKEN=token,
        )
        self.assertEqual(patch.status_code, 200)
        self.flow_staff.refresh_from_db()
        self.staff.refresh_from_db()
        self.assertFalse(self.flow_staff.aktivni)
        self.assertTrue(self.staff.aktivni)

    def test_staff_cannot_edit_own_rozvrh(self):
        token = self._login('staff-i4@test.local', 'Staff1234')
        put = self.client.put(
            '/api/flow/rozvrh/',
            data={'rozvrh': [{'den': i, 'volno': True, 'od': None, 'do': None} for i in range(7)]},
            content_type='application/json',
            HTTP_X_FLOW_TOKEN=token,
        )
        self.assertEqual(put.status_code, 403)

    def test_owner_creates_two_staff_without_login_collision(self):
        token = self._login('owner-i4@test.local', 'Heslo1234')
        a = self.client.post(
            '/api/flow/owner/personal/',
            data={'jmeno': 'Zuzana', 'specializace': 'MakeUP'},
            content_type='application/json',
            HTTP_X_FLOW_TOKEN=token,
        )
        self.assertEqual(a.status_code, 201, a.content)
        b = self.client.post(
            '/api/flow/owner/personal/',
            data={'jmeno': 'Zuzana', 'specializace': 'Vlasy'},
            content_type='application/json',
            HTTP_X_FLOW_TOKEN=token,
        )
        self.assertEqual(b.status_code, 201, b.content)
        self.assertNotEqual(a.json()['prihlasovaci_jmeno'], b.json()['prihlasovaci_jmeno'])

        flow = self.client.post(
            f'/api/flow/owner/personal/{a.json()["id"]}/flow/',
            data={'email': 'zuzana-i4@test.local', 'visible_overview': False},
            content_type='application/json',
            HTTP_X_FLOW_TOKEN=token,
        )
        self.assertEqual(flow.status_code, 201, flow.content)
        self.assertTrue(FlowUser.objects.filter(email='zuzana-i4@test.local').exists())
        zam = Zamestnanec.objects.get(pk=a.json()['id'])
        self.assertEqual(zam.prihlasovaci_jmeno.lower(), 'zuzana-i4@test.local')
        self.assertFalse(flow.json()['email_odeslan'])
        self.assertIn('docasne_heslo', flow.json())
        self.assertTrue(flow.json()['docasne_heslo'])
        self.assertIn('detail', flow.json())

