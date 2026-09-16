"""P5.6B — legacy FLOW kartotéka neexistuje; Archivník a ostatní FLOW zůstávají."""
from __future__ import annotations

import importlib
from datetime import timedelta

from django.apps import apps
from django.conf import settings
from django.db import connection
from django.test import Client, TestCase
from django.urls import resolve
from django.urls.exceptions import Resolver404
from django.utils import timezone

from archivnik.models import Customer
from flow.tests_kartoteka import _flow_ucet, _zapni_archivnik
from rezervace.models import Rezervace, Zamestnanec
from salons.models import CenikPolozka, Salon


class P56bLegacyKartotekaGoneTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.salon = Salon.objects.create(name='P56B Salon', email='p56b@test.local')
        self.owner, self.flow = _flow_ucet(
            self.salon, 'p56b-owner@test.local', 'HesloB123', jmeno='Majitel P56B',
        )
        _zapni_archivnik(self.salon)
        self.customer = Customer.objects.create(
            salon=self.salon,
            jmeno='Jan',
            prijmeni='Novák',
            email='jan.p56b@test.local',
        )
        CenikPolozka.objects.create(
            salon=self.salon, nazev='Střih', cena=500, delka_minut=45, aktivni=True,
        )

    def _login(self):
        r = self.client.post(
            '/api/flow/prihlaseni/',
            data={'email': 'p56b-owner@test.local', 'password': 'HesloB123'},
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 200)
        return r.json()['token']

    def test_modely_nejsou_v_django_apps(self):
        with self.assertRaises(LookupError):
            apps.get_model('flow', 'CustomerCard')
        with self.assertRaises(LookupError):
            apps.get_model('flow', 'CustomerVisit')

    def test_legacy_tabulky_neexistuji(self):
        tables = set(connection.introspection.table_names())
        self.assertNotIn('flow_customercard', tables)
        self.assertNotIn('flow_customervisit', tables)

    def test_moduly_nelze_importovat(self):
        for mod in (
            'flow.customer_card_models',
            'flow.customer_card_views',
            'flow.customer_card_serializers',
            'flow.customer_card_services',
            'flow.customer_card_emails',
        ):
            with self.assertRaises(ModuleNotFoundError):
                importlib.import_module(mod)

    def test_legacy_endpointy_404(self):
        token = self._login()
        paths = (
            '/api/flow/zakaznicke-karty/',
            '/api/flow/zakaznicke-karty/lookup/',
            '/api/flow/zakaznicke-karty/1/',
            '/api/flow/zakaznicke-karty/1/odeslat-potvrzeni/',
            '/api/flow/zakaznicke-karty/1/aktivovat-lokalne/',
            '/api/flow/zakaznicke-karty/1/navstevy/',
            '/api/flow/zakaznicka-karta/potvrdit/abc123/',
        )
        for path in paths:
            with self.assertRaises(Resolver404):
                resolve(path)
            r = self.client.get(path, HTTP_X_FLOW_TOKEN=token)
            self.assertEqual(r.status_code, 404, path)
            r_post = self.client.post(
                path, data={}, content_type='application/json', HTTP_X_FLOW_TOKEN=token,
            )
            self.assertEqual(r_post.status_code, 404, f'POST {path}')

    def test_kalendar_ma_archivnik_uuid_ne_customer_card_id(self):
        now = timezone.now()
        Rezervace.objects.create(
            salon=self.salon,
            zamestnanec=self.owner,
            zacatek=now,
            konec=now + timedelta(hours=1),
            stav='potvrzeno',
            jmeno_host='Jan Novák',
            email_host='jan.p56b@test.local',
        )
        token = self._login()
        r = self.client.get('/api/flow/kalendar/', HTTP_X_FLOW_TOKEN=token)
        self.assertEqual(r.status_code, 200)
        row = r.json()['rezervace'][0]
        self.assertEqual(row['archivnik_customer_uuid'], str(self.customer.uuid))
        self.assertNotIn('customer_card_id', row)

    def test_settings_bez_customer_card(self):
        keys = [k for k in dir(settings) if 'CUSTOMER_CARD' in k]
        self.assertEqual(keys, [])
        self.assertTrue(getattr(settings, 'API_PUBLIC_BASE_URL'))

    def test_confirm_task_neexistuje(self):
        import flow.tasks as flow_tasks
        self.assertFalse(hasattr(flow_tasks, 'task_email_customer_card_confirm'))
        self.assertTrue(hasattr(flow_tasks, 'task_email_flow_pristup'))
        with self.assertRaises(ImportError):
            from flow.tasks import task_email_customer_card_confirm  # noqa: F401

    def test_flow_login_me_kalendar_kartoteka(self):
        token = self._login()
        headers = {'HTTP_X_FLOW_TOKEN': token}
        me = self.client.get('/api/flow/me/', **headers)
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()['email'], 'p56b-owner@test.local')

        kalendar = self.client.get('/api/flow/kalendar/', **headers)
        self.assertEqual(kalendar.status_code, 200)
        self.assertIn('rezervace', kalendar.json())

        sluzby = self.client.get('/api/flow/sluzby/', **headers)
        self.assertEqual(sluzby.status_code, 200)

        rozvrh = self.client.get('/api/flow/rozvrh/', **headers)
        self.assertEqual(rozvrh.status_code, 200)

        absence = self.client.get('/api/flow/absence/', **headers)
        self.assertEqual(absence.status_code, 200)

        personal = self.client.get('/api/flow/owner/personal/', **headers)
        self.assertEqual(personal.status_code, 200)

        list_c = self.client.get('/api/flow/kartoteka/zakaznici/', **headers)
        self.assertEqual(list_c.status_code, 200)
        rows = list_c.json()['vysledky']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['uuid'], str(self.customer.uuid))

        detail = self.client.get(
            f'/api/flow/kartoteka/zakaznici/{self.customer.uuid}/', **headers,
        )
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()['email'], 'jan.p56b@test.local')

    def test_zamestnanec_nevidi_owner_personal(self):
        Zamestnanec.objects.filter(pk=self.owner.pk).update(role=Zamestnanec.ROLE_ZAMESTNANEC)
        token = self._login()
        r = self.client.get('/api/flow/owner/personal/', HTTP_X_FLOW_TOKEN=token)
        self.assertIn(r.status_code, (403, 404))
