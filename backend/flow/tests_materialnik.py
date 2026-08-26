from django.test import Client, TestCase, override_settings

from flow.models import FlowUser
from partner_admin.services_moduly import nastav_modul
from rezervace.models import Zamestnanec
from salons.models import CenikPolozka, Salon


class Actor:
    username = 'test-admin'


@override_settings(MATERIALNIK_STUB=True, MATERIALNIK_M2M_KEY='test-m2m')
class MaterialnikIntegrationsTests(TestCase):
    def setUp(self):
        self.salon = Salon.objects.create(name='Salon SSO')
        self.owner = Zamestnanec.objects.create(
            salon=self.salon,
            jmeno='Manager',
            role=Zamestnanec.ROLE_MAJITEL,
            prihlasovaci_jmeno='majitel-mat@test.local',
            aktivni=True,
        )
        self.owner.set_password('Heslo1234')
        self.owner.save(update_fields=['password_hash'])
        self.flow = FlowUser.objects.create(
            salon=self.salon,
            zamestnanec=self.owner,
            email='majitel-mat@test.local',
            aktivni=True,
        )
        self.flow.password_hash = self.owner.password_hash
        self.flow.save(update_fields=['password_hash'])
        CenikPolozka.objects.create(salon=self.salon, nazev='Střih', cena=300)
        self.client = Client()

    def _login_flow(self):
        r = self.client.post(
            '/api/flow/prihlaseni/',
            data={'email': 'majitel-mat@test.local', 'password': 'Heslo1234'},
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 200)
        return r.json()['token']

    def test_me_bez_modulu_nema_materialnik(self):
        token = self._login_flow()
        me = self.client.get('/api/flow/me/', HTTP_X_FLOW_TOKEN=token)
        self.assertEqual(me.status_code, 200)
        self.assertNotIn('materialnik', me.json().get('moduly') or {})

    def test_me_s_modulem_ma_url(self):
        nastav_modul(self.salon, 'materialnik', True, Actor())
        token = self._login_flow()
        with self.settings(MATERIALNIK_PUBLIC_URL='http://127.0.0.1:8001'):
            me = self.client.get('/api/flow/me/', HTTP_X_FLOW_TOKEN=token)
        self.assertEqual(me.json()['moduly']['materialnik']['url'], 'http://127.0.0.1:8001')

    def test_session_bez_modulu_je_401(self):
        r = self.client.post(
            '/api/integrations/v1/materialnik/session',
            data={'email': 'majitel-mat@test.local', 'password': 'Heslo1234'},
            content_type='application/json',
            HTTP_X_ULOV_M2M_KEY='test-m2m',
        )
        self.assertEqual(r.status_code, 401)

    def test_session_s_modulem_vraci_tenant(self):
        nastav_modul(self.salon, 'materialnik', True, Actor())
        r = self.client.post(
            '/api/integrations/v1/materialnik/session',
            data={'email': 'majitel-mat@test.local', 'password': 'Heslo1234'},
            content_type='application/json',
            HTTP_X_ULOV_M2M_KEY='test-m2m',
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body['salon_id'], self.salon.id)
        self.assertTrue(body['tenant_uuid'])

    def test_session_spatny_m2m(self):
        nastav_modul(self.salon, 'materialnik', True, Actor())
        r = self.client.post(
            '/api/integrations/v1/materialnik/session',
            data={'email': 'majitel-mat@test.local', 'password': 'Heslo1234'},
            content_type='application/json',
            HTTP_X_ULOV_M2M_KEY='spatne',
        )
        self.assertEqual(r.status_code, 401)

    def test_catalog_jen_vlastni_sluzby(self):
        jiny = Salon.objects.create(name='Cizí')
        CenikPolozka.objects.create(salon=jiny, nazev='Cizí služba', cena=1)
        nastav_modul(self.salon, 'materialnik', True, Actor())
        tenant = str(self.salon.partner_nastaveni.tenant_uuid)
        r = self.client.get(
            f'/api/integrations/v1/materialnik/catalog?tenant_uuid={tenant}',
            HTTP_X_ULOV_M2M_KEY='test-m2m',
        )
        self.assertEqual(r.status_code, 200)
        names = [s['name'] for s in r.json()['services']]
        self.assertEqual(names, ['Střih'])
        self.assertTrue(all(s['external_service_id'].startswith('cenik:') for s in r.json()['services']))

    def test_prehled_bez_modulu_je_404(self):
        token = self._login_flow()
        r = self.client.get('/api/flow/materialnik-prehled/', HTTP_X_FLOW_TOKEN=token)
        self.assertEqual(r.status_code, 404)

    def test_prehled_s_modulem_vraci_polozky(self):
        nastav_modul(self.salon, 'materialnik', True, Actor())
        token = self._login_flow()
        r = self.client.get('/api/flow/materialnik-prehled/', HTTP_X_FLOW_TOKEN=token)
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertFalse(body.get('unavailable'))
        self.assertEqual(body.get('items'), [])
        self.assertIn('kpi', body)
