"""I3 — FLOW owner nastavení rezervací."""

from django.test import TestCase, Client

from flow.auth import web_provozovny_url
from flow.models import FlowUser
from partner_admin.models import PartnerNastaveni
from rezervace.models import RezervacniNastaveni, Zamestnanec
from salons.models import Salon


class FlowOwnerNastaveniTests(TestCase):
    def setUp(self):
        self.salon = Salon.objects.create(name='Salon I3')
        self.owner = Zamestnanec.objects.create(
            salon=self.salon,
            jmeno='Owner',
            role=Zamestnanec.ROLE_MAJITEL,
            prihlasovaci_jmeno='owner-i3@test.local',
            aktivni=True,
            zobrazit_na_webu=False,
        )
        self.owner.set_password('Heslo1234')
        self.owner.save(update_fields=['password_hash'])
        self.flow_owner = FlowUser.objects.create(
            salon=self.salon,
            zamestnanec=self.owner,
            email='owner-i3@test.local',
            visible_overview=True,
            aktivni=True,
        )
        self.flow_owner.password_hash = self.owner.password_hash
        self.flow_owner.save(update_fields=['password_hash'])

        self.staff = Zamestnanec.objects.create(
            salon=self.salon,
            jmeno='Staff',
            role=Zamestnanec.ROLE_ZAMESTNANEC,
            prihlasovaci_jmeno='staff-i3',
            aktivni=True,
            zobrazit_na_webu=True,
        )
        self.flow_staff = FlowUser.objects.create(
            salon=self.salon,
            zamestnanec=self.staff,
            email='staff-i3@test.local',
            aktivni=True,
        )
        self.flow_staff.set_password('Staff1234')
        self.flow_staff.save(update_fields=['password_hash'])
        RezervacniNastaveni.objects.get_or_create(salon=self.salon)
        partner, _ = PartnerNastaveni.objects.get_or_create(salon=self.salon)
        partner.povolit_technicke_nastaveni = True
        partner.save(update_fields=['povolit_technicke_nastaveni'])
        self.client = Client()

    def _login(self, email, password):
        r = self.client.post(
            '/api/flow/prihlaseni/',
            data={'email': email, 'password': password},
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 200)
        return r.json()['token']

    def test_owner_can_get_and_put_pravidla(self):
        token = self._login('owner-i3@test.local', 'Heslo1234')
        get = self.client.get('/api/flow/owner/nastaveni/', HTTP_X_FLOW_TOKEN=token)
        self.assertEqual(get.status_code, 200)
        self.assertNotIn('gdpr_zasady_verze', get.json())

        put = self.client.put(
            '/api/flow/owner/nastaveni/',
            data={
                'interval_minut': 10,
                'min_predstih_hodin': 3,
                'max_predstih_mesicu': 2,
                'storno_do_hodin': 12,
                'potvrzeni_platnost_hodin': 48,
                'auto_potvrzeni': True,
                'recenze_url': 'https://example.com/recenze',
                'gdpr_zasady_verze': '99.9',
            },
            content_type='application/json',
            HTTP_X_FLOW_TOKEN=token,
        )
        self.assertEqual(put.status_code, 200)
        body = put.json()
        self.assertEqual(body['interval_minut'], 10)
        self.assertEqual(body['min_predstih_hodin'], 3)
        self.assertTrue(body['auto_potvrzeni'])
        self.assertNotIn('gdpr_zasady_verze', body)
        nast = RezervacniNastaveni.objects.get(salon=self.salon)
        self.assertNotEqual(nast.gdpr_zasady_verze, '99.9')
        me = self.client.get('/api/flow/me/', HTTP_X_FLOW_TOKEN=token)
        self.assertTrue(me.json().get('povolit_technicke_nastaveni'))

    def test_technicke_nastaveni_blocked_when_disabled(self):
        PartnerNastaveni.objects.filter(salon=self.salon).update(
            povolit_technicke_nastaveni=False,
        )
        token = self._login('owner-i3@test.local', 'Heslo1234')
        me = self.client.get('/api/flow/me/', HTTP_X_FLOW_TOKEN=token)
        self.assertFalse(me.json().get('povolit_technicke_nastaveni'))
        get = self.client.get('/api/flow/owner/nastaveni/', HTTP_X_FLOW_TOKEN=token)
        self.assertEqual(get.status_code, 403)
        audit = self.client.get('/api/flow/owner/audit-log/', HTTP_X_FLOW_TOKEN=token)
        self.assertEqual(audit.status_code, 403)

    def test_staff_forbidden(self):
        token = self._login('staff-i3@test.local', 'Staff1234')
        get = self.client.get('/api/flow/owner/nastaveni/', HTTP_X_FLOW_TOKEN=token)
        self.assertEqual(get.status_code, 403)

    def test_me_web_url_when_domena_filled(self):
        PartnerNastaveni.objects.filter(salon=self.salon).update(domena='demo3.ulovklienty.cz')
        token = self._login('owner-i3@test.local', 'Heslo1234')
        me = self.client.get('/api/flow/me/', HTTP_X_FLOW_TOKEN=token)
        salon = me.json()['salon']
        self.assertEqual(salon['domena'], 'demo3.ulovklienty.cz')
        self.assertEqual(salon['web_url'], 'https://demo3.ulovklienty.cz')

    def test_me_web_url_empty_without_domena(self):
        PartnerNastaveni.objects.filter(salon=self.salon).update(domena='')
        token = self._login('staff-i3@test.local', 'Staff1234')
        me = self.client.get('/api/flow/me/', HTTP_X_FLOW_TOKEN=token)
        salon = me.json()['salon']
        self.assertEqual(salon['domena'], '')
        self.assertEqual(salon['web_url'], '')

    def test_web_provozovny_url_helper(self):
        self.assertEqual(
            web_provozovny_url('https://Demo3.ulovklienty.cz/'),
            'https://demo3.ulovklienty.cz',
        )
        self.assertEqual(web_provozovny_url(''), '')
        self.assertEqual(web_provozovny_url('evil.cz/cesta'), '')
