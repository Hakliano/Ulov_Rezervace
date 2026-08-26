"""Přehled FLOW — tržby z dokončených služeb a přístup s Visible Overview."""

from datetime import timedelta

from django.test import Client, TestCase
from django.utils import timezone

from flow.models import FlowUser
from rezervace.models import Rezervace, RezervaceSluzba, Zamestnanec
from salons.models import CenikPolozka, Salon


class FlowPrehledStatistikyTests(TestCase):
    def setUp(self):
        self.salon = Salon.objects.create(name='Salon Prehled')
        self.owner = Zamestnanec.objects.create(
            salon=self.salon,
            jmeno='Owner',
            role=Zamestnanec.ROLE_MAJITEL,
            prihlasovaci_jmeno='owner-prehled@test.local',
            aktivni=True,
            zobrazit_na_webu=False,
        )
        self.owner.set_password('Heslo1234')
        self.owner.save(update_fields=['password_hash'])
        self.flow_owner = FlowUser.objects.create(
            salon=self.salon,
            zamestnanec=self.owner,
            email='owner-prehled@test.local',
            aktivni=True,
            visible_overview=True,
        )
        self.flow_owner.password_hash = self.owner.password_hash
        self.flow_owner.save(update_fields=['password_hash'])

        self.anna = Zamestnanec.objects.create(
            salon=self.salon,
            jmeno='Anna Test',
            fotka='https://example.com/anna.webp',
            role=Zamestnanec.ROLE_ZAMESTNANEC,
            prihlasovaci_jmeno='anna-prehled',
            aktivni=True,
        )
        self.flow_staff = FlowUser.objects.create(
            salon=self.salon,
            zamestnanec=self.anna,
            email='anna-prehled@test.local',
            aktivni=True,
            visible_overview=False,
        )
        self.flow_staff.set_password('Staff1234')
        self.flow_staff.save(update_fields=['password_hash'])

        self.sluzba = CenikPolozka.objects.create(
            salon=self.salon, nazev='Střih', cena=500, delka_minut=60, aktivni=True,
        )
        now = timezone.now()
        rez = Rezervace.objects.create(
            salon=self.salon,
            zamestnanec=self.anna,
            zacatek=now,
            konec=now + timedelta(hours=1),
            stav='dokonceno',
            jmeno_host='Klient',
        )
        RezervaceSluzba.objects.create(rezervace=rez, sluzba=self.sluzba)
        self.client = Client()

    def _login(self, email, password):
        r = self.client.post(
            '/api/flow/prihlaseni/',
            data={'email': email, 'password': password},
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 200)
        return r.json()['token']

    def test_owner_vidi_trzbu_a_fotku(self):
        token = self._login('owner-prehled@test.local', 'Heslo1234')
        r = self.client.get('/api/flow/owner/statistiky/', HTTP_X_FLOW_TOKEN=token)
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body['trzba_celkem'], 500)
        self.assertEqual(body['trzba_mesic'], 500)
        self.assertEqual(body['dokonceno'], 1)
        anna = next(p for p in body['zamestnanci'] if p['jmeno'] == 'Anna Test')
        self.assertEqual(anna['fotka'], 'https://example.com/anna.webp')
        self.assertEqual(anna['trzba'], 500)
        self.assertEqual(anna['dokonceno'], 1)

    def test_staff_bez_overview_vidi_svoje(self):
        jina = Zamestnanec.objects.create(
            salon=self.salon,
            jmeno='Bára Cizí',
            role=Zamestnanec.ROLE_ZAMESTNANEC,
            prihlasovaci_jmeno='bara-prehled',
            aktivni=True,
        )
        now = timezone.now()
        cizi = Rezervace.objects.create(
            salon=self.salon,
            zamestnanec=jina,
            zacatek=now + timedelta(hours=2),
            konec=now + timedelta(hours=3),
            stav='dokonceno',
            jmeno_host='Cizí klient',
        )
        RezervaceSluzba.objects.create(rezervace=cizi, sluzba=self.sluzba)
        token = self._login('anna-prehled@test.local', 'Staff1234')
        r = self.client.get('/api/flow/owner/statistiky/', HTTP_X_FLOW_TOKEN=token)
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body['rozsah'], 'moje')
        self.assertEqual(body['trzba_celkem'], 500)
        self.assertEqual(body['dokonceno'], 1)
        self.assertEqual(body['zamestnanci'], [])

    def test_staff_s_overview_ok(self):
        self.flow_staff.visible_overview = True
        self.flow_staff.save(update_fields=['visible_overview'])
        token = self._login('anna-prehled@test.local', 'Staff1234')
        r = self.client.get('/api/flow/owner/statistiky/', HTTP_X_FLOW_TOKEN=token)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['trzba_celkem'], 500)
