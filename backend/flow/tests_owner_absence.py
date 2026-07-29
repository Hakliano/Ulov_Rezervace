"""I5 — schvalování absencí majitelem."""

from datetime import date, timedelta

from django.test import TestCase, Client
from django.utils import timezone

from flow.models import FlowUser
from rezervace.models import Rezervace, Zamestnanec, ZamestnanecAbsence, ZamestnanecRozvrh
from rezervace.services.availability import zamestnanec_dostupny
from salons.models import Salon


class FlowOwnerAbsenceTests(TestCase):
    def setUp(self):
        self.salon = Salon.objects.create(name='Salon I5')
        self.owner = Zamestnanec.objects.create(
            salon=self.salon,
            jmeno='Owner',
            role=Zamestnanec.ROLE_MAJITEL,
            prihlasovaci_jmeno='owner-i5@test.local',
            aktivni=True,
            zobrazit_na_webu=False,
        )
        self.owner.set_password('Heslo1234')
        self.owner.save(update_fields=['password_hash'])
        self.flow_owner = FlowUser.objects.create(
            salon=self.salon,
            zamestnanec=self.owner,
            email='owner-i5@test.local',
            aktivni=True,
            visible_overview=True,
        )
        self.flow_owner.password_hash = self.owner.password_hash
        self.flow_owner.save(update_fields=['password_hash'])

        self.staff = Zamestnanec.objects.create(
            salon=self.salon,
            jmeno='Staff',
            role=Zamestnanec.ROLE_ZAMESTNANEC,
            prihlasovaci_jmeno='staff-i5@test.local',
            aktivni=True,
            zobrazit_na_webu=True,
        )
        self.staff.set_password('Staff1234')
        self.staff.save(update_fields=['password_hash'])
        for den in range(7):
            ZamestnanecRozvrh.objects.create(
                zamestnanec=self.staff, den=den, od='09:00', do='17:00', volno=False,
            )
        self.flow_staff = FlowUser.objects.create(
            salon=self.salon,
            zamestnanec=self.staff,
            email='staff-i5@test.local',
            aktivni=True,
        )
        self.flow_staff.set_password('Staff1234')
        self.flow_staff.save(update_fields=['password_hash'])
        self.client = Client()
        self.den = date.today() + timedelta(days=14)

    def _login(self, email, password):
        r = self.client.post(
            '/api/flow/prihlaseni/',
            data={'email': email, 'password': password},
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()['token']

    def test_staff_request_pending_does_not_block(self):
        token = self._login('staff-i5@test.local', 'Staff1234')
        r = self.client.post(
            '/api/flow/absence/',
            data={
                'datum_od': self.den.isoformat(),
                'datum_do': self.den.isoformat(),
                'typ': 'dovolena',
                'poznamka': 'test',
            },
            content_type='application/json',
            HTTP_X_FLOW_TOKEN=token,
        )
        self.assertEqual(r.status_code, 201, r.content)
        body = r.json()
        self.assertTrue(body['ceka_na_schvaleni'])
        self.assertEqual(body['absence']['stav'], 'ceka')
        self.assertTrue(zamestnanec_dostupny(self.staff, self.den))

        owner_token = self._login('owner-i5@test.local', 'Heslo1234')
        listing = self.client.get(
            '/api/flow/owner/absence/?stav=ceka',
            HTTP_X_FLOW_TOKEN=owner_token,
        )
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()['ceka_pocet'], 1)

        abs_id = body['absence']['id']
        ok = self.client.post(
            f'/api/flow/owner/absence/{abs_id}/schvalit/',
            data={},
            content_type='application/json',
            HTTP_X_FLOW_TOKEN=owner_token,
        )
        self.assertEqual(ok.status_code, 200, ok.content)
        self.assertEqual(ok.json()['absence']['stav'], 'schvaleno')
        self.assertFalse(zamestnanec_dostupny(self.staff, self.den))

    def test_owner_can_reject(self):
        token = self._login('staff-i5@test.local', 'Staff1234')
        r = self.client.post(
            '/api/flow/absence/',
            data={
                'datum_od': self.den.isoformat(),
                'datum_do': self.den.isoformat(),
                'typ': 'nemoc',
            },
            content_type='application/json',
            HTTP_X_FLOW_TOKEN=token,
        )
        abs_id = r.json()['absence']['id']
        owner_token = self._login('owner-i5@test.local', 'Heslo1234')
        no = self.client.post(
            f'/api/flow/owner/absence/{abs_id}/zamitnout/',
            data={},
            content_type='application/json',
            HTTP_X_FLOW_TOKEN=owner_token,
        )
        self.assertEqual(no.status_code, 200)
        self.assertEqual(no.json()['absence']['stav'], 'zamitnuto')
        self.assertTrue(zamestnanec_dostupny(self.staff, self.den))

    def test_me_includes_pending_count_for_owner(self):
        ZamestnanecAbsence.objects.create(
            zamestnanec=self.staff,
            datum_od=self.den,
            datum_do=self.den,
            typ='dovolena',
            stav=ZamestnanecAbsence.STAV_CEKA,
        )
        token = self._login('owner-i5@test.local', 'Heslo1234')
        me = self.client.get('/api/flow/me/', HTTP_X_FLOW_TOKEN=token)
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()['ceka_volno_pocet'], 1)
