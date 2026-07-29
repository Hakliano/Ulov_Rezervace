"""Přiřazení služeb k personálu + filtr termínů."""

from datetime import date, time, timedelta

from django.test import Client, TestCase
from django.utils import timezone

from flow.models import FlowUser
from rezervace.models import RezervacniNastaveni, Zamestnanec, ZamestnanecRozvrh, ZamestnanecSluzba
from rezervace.services.availability import generuj_terminy, zamestnanec_umi_sluzby
from salons.models import CenikPolozka, OteviraciDoba, Salon


class FlowOwnerPrirazeniTests(TestCase):
    def setUp(self):
        self.salon = Salon.objects.create(name='Salon Prirazeni')
        for den in range(7):
            OteviraciDoba.objects.create(
                salon=self.salon, den=den, od=time(9, 0), do=time(17, 0), zavreno=False,
            )
        RezervacniNastaveni.objects.create(
            salon=self.salon,
            interval_minut=60,
            min_predstih_hodin=0,
            max_predstih_mesicu=3,
        )
        self.owner = Zamestnanec.objects.create(
            salon=self.salon,
            jmeno='Owner',
            role=Zamestnanec.ROLE_MAJITEL,
            prihlasovaci_jmeno='owner-prirazeni@test.local',
            aktivni=True,
            zobrazit_na_webu=False,
        )
        self.owner.set_password('Heslo1234')
        self.owner.save(update_fields=['password_hash'])
        self.flow_owner = FlowUser.objects.create(
            salon=self.salon,
            zamestnanec=self.owner,
            email='owner-prirazeni@test.local',
            aktivni=True,
            visible_overview=True,
        )
        self.flow_owner.password_hash = self.owner.password_hash
        self.flow_owner.save(update_fields=['password_hash'])

        self.anna = Zamestnanec.objects.create(
            salon=self.salon,
            jmeno='Anna',
            role=Zamestnanec.ROLE_ZAMESTNANEC,
            aktivni=True,
            prihlasovaci_jmeno='anna-prirazeni',
        )
        self.berta = Zamestnanec.objects.create(
            salon=self.salon,
            jmeno='Berta',
            role=Zamestnanec.ROLE_ZAMESTNANEC,
            aktivni=True,
            prihlasovaci_jmeno='berta-prirazeni',
        )
        for z in (self.anna, self.berta):
            for den in range(5):
                ZamestnanecRozvrh.objects.create(
                    zamestnanec=z, den=den, od=time(9, 0), do=time(17, 0), volno=False,
                )

        self.strih = CenikPolozka.objects.create(
            salon=self.salon, nazev='Střih', cena=500, delka_minut=60, aktivni=True, poradi=1,
        )
        self.barva = CenikPolozka.objects.create(
            salon=self.salon, nazev='Barva', cena=900, delka_minut=60, aktivni=True, poradi=2,
        )
        self.client = Client()

    def _token(self):
        res = self.client.post(
            '/api/flow/prihlaseni/',
            data={'email': 'owner-prirazeni@test.local', 'password': 'Heslo1234'},
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 200)
        return res.json()['token']

    def test_empty_assignment_means_all_services(self):
        self.assertTrue(zamestnanec_umi_sluzby(self.anna, [self.strih.id, self.barva.id]))

    def test_partial_assignment_filters(self):
        ZamestnanecSluzba.objects.create(zamestnanec=self.anna, sluzba=self.strih)
        self.assertTrue(zamestnanec_umi_sluzby(self.anna, [self.strih.id]))
        self.assertFalse(zamestnanec_umi_sluzby(self.anna, [self.barva.id]))
        self.assertFalse(zamestnanec_umi_sluzby(self.anna, [self.strih.id, self.barva.id]))
        # Berta bez řádků stále umí vše
        self.assertTrue(zamestnanec_umi_sluzby(self.berta, [self.barva.id]))

    def test_api_get_put_matrix(self):
        token = self._token()
        listing = self.client.get('/api/flow/owner/prirazeni-sluzeb/', HTTP_X_FLOW_TOKEN=token)
        self.assertEqual(listing.status_code, 200)
        body = listing.json()
        self.assertEqual(len(body['zamestnanci']), 2)
        self.assertEqual(len(body['sluzby']), 2)

        put = self.client.put(
            '/api/flow/owner/prirazeni-sluzeb/',
            data={
                'prirazeni': {
                    str(self.anna.id): [self.strih.id],
                    str(self.berta.id): [self.barva.id],
                },
            },
            content_type='application/json',
            HTTP_X_FLOW_TOKEN=token,
        )
        self.assertEqual(put.status_code, 200)
        self.assertEqual(put.json()['prirazeni'][str(self.anna.id)], [self.strih.id])
        self.assertEqual(
            set(ZamestnanecSluzba.objects.filter(zamestnanec=self.anna).values_list('sluzba_id', flat=True)),
            {self.strih.id},
        )

    def test_generuj_terminy_respektuje_prirazeni(self):
        ZamestnanecSluzba.objects.create(zamestnanec=self.anna, sluzba=self.strih)
        ZamestnanecSluzba.objects.create(zamestnanec=self.berta, sluzba=self.barva)

        # příští pracovní den (Po–Pá)
        d = timezone.localdate() + timedelta(days=1)
        while d.weekday() > 4:
            d += timedelta(days=1)

        terminy_strih = generuj_terminy(self.salon, d, [self.strih.id])
        if terminy_strih:
            dostupni = terminy_strih[0].get('dostupni') or []
            ids = {x['id'] for x in dostupni}
            self.assertIn(self.anna.id, ids)
            self.assertNotIn(self.berta.id, ids)

        terminy_oba = generuj_terminy(self.salon, d, [self.strih.id, self.barva.id])
        # nikdo neumí obě → žádný slot s „Kdokoliv“
        self.assertEqual(terminy_oba, [])
