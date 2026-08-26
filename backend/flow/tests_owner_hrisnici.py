"""Hříšníci — ručně zablokovaný e-mail musí být vidět v seznamu."""

from django.test import Client, TestCase
from django.utils import timezone

from flow.models import FlowUser
from rezervace.models import NoShowZaznam, Zakaznik, Zamestnanec
from rezervace.services.email_reputace import blokovat_v_salonu, hledat_hrisniky
from salons.models import Salon


class OwnerHrisniciTests(TestCase):
    def setUp(self):
        self.salon = Salon.objects.create(name='Salon Hrisnici')
        self.jiny = Salon.objects.create(name='Cizi salon')
        self.owner = Zamestnanec.objects.create(
            salon=self.salon,
            jmeno='Owner',
            role=Zamestnanec.ROLE_MAJITEL,
            prihlasovaci_jmeno='owner-hrisnici@test.local',
            aktivni=True,
            zobrazit_na_webu=False,
        )
        self.owner.set_password('Heslo1234')
        self.owner.save(update_fields=['password_hash'])
        self.flow = FlowUser.objects.create(
            salon=self.salon,
            zamestnanec=self.owner,
            email='owner-hrisnici@test.local',
            aktivni=True,
            visible_overview=True,
        )
        self.flow.password_hash = self.owner.password_hash
        self.flow.save(update_fields=['password_hash'])
        self.client = Client()

    def _login(self):
        r = self.client.post(
            '/api/flow/prihlaseni/',
            data={'email': 'owner-hrisnici@test.local', 'password': 'Heslo1234'},
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 200)
        return r.json()['token']

    def test_rucni_blokace_je_v_seznamu_i_bez_noshow(self):
        blokovat_v_salonu('a@example.com', self.salon.id)
        blokovat_v_salonu('b@example.com', self.salon.id)
        data = hledat_hrisniky(salon_id=self.salon.id)
        emails = {z['email'] for z in data['vysledky']}
        self.assertEqual(emails, {'a@example.com', 'b@example.com'})
        self.assertEqual(data['celkem'], 2)
        for z in data['vysledky']:
            self.assertTrue(z['blokovan_v_salonu'])
            self.assertEqual(z['pocet_no_show'], 0)

    def test_cizi_salon_nevidi_cizi_blokace(self):
        blokovat_v_salonu('cizi@example.com', self.jiny.id)
        data = hledat_hrisniky(salon_id=self.salon.id)
        self.assertEqual(data['celkem'], 0)

    def test_hledani_najde_rucne_zablokovaneho(self):
        blokovat_v_salonu('petra.nova@example.com', self.salon.id)
        blokovat_v_salonu('jiny@example.com', self.salon.id)
        data = hledat_hrisniky(q='petra', salon_id=self.salon.id)
        self.assertEqual(data['celkem'], 1)
        self.assertEqual(data['vysledky'][0]['email'], 'petra.nova@example.com')

    def test_noshow_a_rucni_blokace_se_neslouci_dvakrat(self):
        now = timezone.now()
        NoShowZaznam.objects.create(
            salon=self.salon,
            jmeno='Petra',
            email='petra@example.com',
            zacatek=now,
        )
        blokovat_v_salonu('petra@example.com', self.salon.id)
        data = hledat_hrisniky(salon_id=self.salon.id)
        self.assertEqual(data['celkem'], 1)
        row = data['vysledky'][0]
        self.assertEqual(row['email'], 'petra@example.com')
        self.assertEqual(row['pocet_no_show'], 1)
        self.assertTrue(row['blokovan_v_salonu'])

    def test_api_blokace_a_archiv(self):
        token = self._login()
        blok = self.client.post(
            '/api/flow/owner/no-show-blokovat/',
            data={'email': 'novy@example.com'},
            content_type='application/json',
            HTTP_X_FLOW_TOKEN=token,
        )
        self.assertEqual(blok.status_code, 200)
        self.assertTrue(Zakaznik.objects.filter(
            salon=self.salon, email='novy@example.com', blokovan=True,
        ).exists())
        archiv = self.client.get(
            '/api/flow/owner/no-show-archiv/',
            HTTP_X_FLOW_TOKEN=token,
        )
        self.assertEqual(archiv.status_code, 200)
        body = archiv.json()
        self.assertEqual(body['celkem'], 1)
        self.assertEqual(body['vysledky'][0]['email'], 'novy@example.com')
        self.assertTrue(body['vysledky'][0]['blokovan_v_salonu'])
