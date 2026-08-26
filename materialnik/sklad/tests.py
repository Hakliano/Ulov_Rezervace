from uuid import uuid4
from decimal import Decimal
from unittest.mock import patch

from django.test import Client, TestCase, override_settings
from django.utils import timezone

from sklad.crypto import new_hmac_key, sign, body_canonical, key_hash
from sklad.models import (
    InboxEvent,
    Material,
    Recipe,
    RecipeLine,
    ServiceMapping,
    StaffSession,
    StockMovement,
    Tenant,
    TenantCredential,
    Unit,
)
from sklad.services import seed_units, stock_qty
from sklad.tenant import set_tenant_id


@override_settings(MATERIALNIK_M2M_KEY='test-m2m')
class IsolationTests(TestCase):
    def setUp(self):
        seed_units()
        self.unit = Unit.objects.get(code='ml')
        self.tenant_a = Tenant.objects.create(
            id=uuid4(), name_snapshot='Salon A', status=Tenant.STAV_ACTIVE,
            activated_at=timezone.now(),
        )
        self.tenant_b = Tenant.objects.create(
            id=uuid4(), name_snapshot='Salon B', status=Tenant.STAV_ACTIVE,
            activated_at=timezone.now(),
        )
        self.secret_a = new_hmac_key()
        TenantCredential.objects.create(
            tenant=self.tenant_a, secret=self.secret_a, key_hash=key_hash(self.secret_a),
        )
        secret_b = new_hmac_key()
        TenantCredential.objects.create(
            tenant=self.tenant_b, secret=secret_b, key_hash=key_hash(secret_b),
        )
        set_tenant_id(self.tenant_a.id)
        self.mat_a = Material.objects.create(
            tenant=self.tenant_a, name='Barva A', unit=self.unit, min_quantity=10,
        )
        set_tenant_id(self.tenant_b.id)
        self.mat_b = Material.objects.create(
            tenant=self.tenant_b, name='Barva B', unit=self.unit, min_quantity=10,
        )
        set_tenant_id(None)
        self.session_a = StaffSession.issue(self.tenant_a, {'id': 1, 'jmeno': 'Anna', 'je_majitel': True})
        self.session_b = StaffSession.issue(self.tenant_b, {'id': 2, 'jmeno': 'Bára', 'je_majitel': True})
        self.client = Client()

    def _login(self, session):
        self.client.cookies['materialnik_token'] = session.token

    def test_a_nevidi_material_b(self):
        self._login(self.session_a)
        r = self.client.get('/materialy/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Barva A')
        self.assertNotContains(r, 'Barva B')

    def test_url_id_ciziho_materialu_je_404(self):
        self._login(self.session_a)
        r = self.client.get(f'/materialy/{self.mat_b.pk}/')
        self.assertEqual(r.status_code, 404)

    def test_post_na_cizi_material_neodečte(self):
        self._login(self.session_a)
        r = self.client.post('/spotreba/', {'material': self.mat_b.pk, 'quantity': '5'})
        self.assertEqual(r.status_code, 404)
        set_tenant_id(self.tenant_b.id)
        self.assertEqual(stock_qty(self.mat_b), 0)

    def test_provision_vytvori_tenanta(self):
        uid = str(uuid4())
        r = self.client.post(
            '/v1/internal/tenants',
            data={'tenant_uuid': uid, 'salon_id': 99, 'name': 'Nový', 'external_tenant_id': 'salon:99'},
            content_type='application/json',
            HTTP_X_ULOV_M2M_KEY='test-m2m',
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['status'], 'active')
        self.assertTrue(Tenant.objects.filter(pk=uid).exists())

    def test_stock_summary_vraci_jen_vlastni_pod_minimem(self):
        r = self.client.post(
            '/v1/internal/stock-summary',
            data={
                'tenant_uuid': str(self.tenant_a.id),
                'hmac_key': self.secret_a,
            },
            content_type='application/json',
            HTTP_X_ULOV_M2M_KEY='test-m2m',
        )
        self.assertEqual(r.status_code, 200)
        body = r.json()
        names = [i['name'] for i in body['items']]
        self.assertIn('Barva A', names)
        self.assertNotIn('Barva B', names)
        self.assertEqual(body['kpi']['critical'], 1)
        self.assertEqual(body['kpi']['below'], 1)
        self.assertEqual(body['items'][0]['status'], 'critical')

    def test_event_cizi_sluzby_je_odmitnut(self):
        payload = {
            'event_id': 'evt-1' + 'a' * 58,
            'event_type': 'service.completed',
            'occurred_at': timezone.now().isoformat(),
            'tenant_uuid': str(self.tenant_a.id),
            'payload': {
                'reservation_ref': 'rezervace:1',
                'services': [{'external_service_id': 'cenik:999', 'name': 'Cizí', 'quantity': 1}],
            },
        }
        ts = payload['occurred_at']
        body = body_canonical(payload)
        sig = sign(self.secret_a, ts, payload['event_id'], body)
        r = self.client.post(
            '/v1/events',
            data=body,
            content_type='application/json',
            HTTP_X_TIMESTAMP=ts,
            HTTP_X_SIGNATURE=sig,
        )
        self.assertEqual(r.status_code, 403)
        self.assertEqual(StockMovement.unscoped.filter(tenant=self.tenant_a).count(), 0)
        self.assertEqual(
            InboxEvent.objects.get(event_id=payload['event_id']).reject_reason,
            'service_not_in_tenant',
        )

    def test_spatny_podpis_401(self):
        payload = {
            'event_id': 'b' * 64,
            'event_type': 'service.completed',
            'occurred_at': timezone.now().isoformat(),
            'tenant_uuid': str(self.tenant_a.id),
            'payload': {'reservation_ref': 'rezervace:2', 'services': []},
        }
        ts = payload['occurred_at']
        body = body_canonical(payload)
        r = self.client.post(
            '/v1/events',
            data=body,
            content_type='application/json',
            HTTP_X_TIMESTAMP=ts,
            HTTP_X_SIGNATURE='0' * 64,
        )
        self.assertEqual(r.status_code, 401)

    def test_duplicitni_event_neodečte_dvakrat(self):
        set_tenant_id(self.tenant_a.id)
        ServiceMapping.objects.create(
            tenant=self.tenant_a,
            external_service_id='cenik:1',
            name_snapshot='Střih',
        )
        payload = {
            'event_id': 'c' * 64,
            'event_type': 'service.completed',
            'occurred_at': timezone.now().isoformat(),
            'tenant_uuid': str(self.tenant_a.id),
            'payload': {
                'reservation_ref': 'rezervace:3',
                'services': [{'external_service_id': 'cenik:1', 'name': 'Střih', 'quantity': 1}],
            },
        }
        ts = payload['occurred_at']
        body = body_canonical(payload)
        sig = sign(self.secret_a, ts, payload['event_id'], body)
        headers = {
            'HTTP_X_TIMESTAMP': ts,
            'HTTP_X_SIGNATURE': sig,
        }
        r1 = self.client.post('/v1/events', data=body, content_type='application/json', **headers)
        r2 = self.client.post('/v1/events', data=body, content_type='application/json', **headers)
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        self.assertTrue(r2.json().get('duplicate'))
        # bez receptury 0 pohybů, ale inbox jen jednou processed + druhé duplicate odpověď bez druhého inbox fail
        self.assertEqual(InboxEvent.objects.filter(event_id=payload['event_id']).count(), 1)


class RecipeEditTests(TestCase):
    def setUp(self):
        seed_units()
        self.unit = Unit.objects.get(code='ml')
        self.tenant = Tenant.objects.create(
            id=uuid4(), name_snapshot='Salon Rec', status=Tenant.STAV_ACTIVE,
            activated_at=timezone.now(),
        )
        self.other = Tenant.objects.create(
            id=uuid4(), name_snapshot='Salon Other', status=Tenant.STAV_ACTIVE,
            activated_at=timezone.now(),
        )
        set_tenant_id(self.tenant.id)
        self.mat = Material.objects.create(
            tenant=self.tenant, name='Barva 6.1', unit=self.unit, min_quantity=10,
        )
        self.mat2 = Material.objects.create(
            tenant=self.tenant, name='Oxidant 6 %', unit=self.unit, min_quantity=10,
        )
        self.mapping = ServiceMapping.objects.create(
            tenant=self.tenant, source='modernik-flow',
            external_service_id='svc-barva', name_snapshot='Barva',
        )
        set_tenant_id(self.other.id)
        self.other_mat = Material.objects.create(
            tenant=self.other, name='Cizí barva', unit=self.unit, min_quantity=10,
        )
        self.other_map = ServiceMapping.objects.create(
            tenant=self.other, source='modernik-flow',
            external_service_id='svc-other', name_snapshot='Cizí služba',
        )
        set_tenant_id(None)
        self.session = StaffSession.issue(self.tenant, {'id': 1, 'jmeno': 'Anna', 'je_majitel': True})
        self.client = Client()
        self.client.cookies['materialnik_token'] = self.session.token
        self.patcher = patch('sklad.views.ulov_catalog', return_value=[])
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_list_ma_novou_recepturu_a_bez_spodniho_formulare(self):
        r = self.client.get('/receptury/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Přidat ke službě')
        self.assertNotContains(r, 'Přidat do receptury')

    def test_create_and_edit_recipe(self):
        create = self.client.post('/receptury/nova/', {
            'mapping': str(self.mapping.pk),
            'material': [str(self.mat.pk), str(self.mat2.pk)],
            'quantity': ['60', '90'],
        })
        self.assertEqual(create.status_code, 302, create.content)
        set_tenant_id(self.tenant.id)
        rec = Recipe.objects.get(service_mapping=self.mapping)
        self.assertEqual(rec.lines.count(), 2)
        set_tenant_id(None)

        edit_page = self.client.get(f'/receptury/{rec.pk}/')
        self.assertEqual(edit_page.status_code, 200)
        self.assertContains(edit_page, 'Upravit seznam')
        self.assertContains(edit_page, 'Barva')

        save = self.client.post(f'/receptury/{rec.pk}/', {
            'material': [str(self.mat.pk)],
            'quantity': ['40'],
        })
        self.assertEqual(save.status_code, 302)
        set_tenant_id(self.tenant.id)
        rec.refresh_from_db()
        self.assertEqual(rec.lines.count(), 1)
        self.assertEqual(rec.lines.get().quantity, Decimal('40'))
        set_tenant_id(None)

    def test_cizi_receptura_je_404(self):
        set_tenant_id(self.other.id)
        rec = Recipe.objects.create(tenant=self.other, service_mapping=self.other_map)
        set_tenant_id(None)
        r = self.client.get(f'/receptury/{rec.pk}/')
        self.assertEqual(r.status_code, 404)

    def test_nelze_pridat_cizi_material_do_receptury(self):
        r = self.client.post('/receptury/nova/', {
            'mapping': str(self.mapping.pk),
            'material': [str(self.other_mat.pk)],
            'quantity': ['10'],
        })
        self.assertEqual(r.status_code, 404)
        set_tenant_id(self.tenant.id)
        self.assertFalse(Recipe.objects.filter(service_mapping=self.mapping).exists())
        set_tenant_id(None)

    def test_palette_without_qty_and_no_auto_consume(self):
        from sklad.services import auto_consume_from_event, recipe_lines_for_services

        r = self.client.post('/receptury/nova/', {
            'mapping': str(self.mapping.pk),
            'material': [str(self.mat.pk), str(self.mat2.pk)],
            'quantity': ['', '90'],
        })
        self.assertEqual(r.status_code, 302, r.content)
        set_tenant_id(self.tenant.id)
        rec = Recipe.objects.get(service_mapping=self.mapping)
        by_mat = {line.material_id: line.quantity for line in rec.lines.all()}
        self.assertIsNone(by_mat[self.mat.id])
        self.assertEqual(by_mat[self.mat2.id], Decimal('90'))
        lines = recipe_lines_for_services(self.tenant, [{
            'external_service_id': 'svc-barva', 'name': 'Barva', 'quantity': 1,
        }])
        self.assertEqual(len(lines), 2)
        empty = next(x for x in lines if x['material_id'] == str(self.mat.id))
        self.assertEqual(empty['actual_qty'], '')
        self.assertEqual(empty['recipe_qty'], '')
        typical = next(x for x in lines if x['material_id'] == str(self.mat2.id))
        self.assertEqual(typical['recipe_qty'], '90')
        self.assertEqual(typical['actual_qty'], '')
        auto = auto_consume_from_event(self.tenant, {
            'payload': {
                'reservation_ref': 'rezervace:9',
                'services': [{'external_service_id': 'svc-barva', 'quantity': 1}],
            },
        }, 'evt-1')
        self.assertEqual(auto['movements'], 0)
        self.assertEqual(stock_qty(self.mat), 0)
        set_tenant_id(None)


