"""P5.6A — výmaz kartotéky, servisní exporty, banner, žádný partner bulk export."""

from __future__ import annotations

import json
import zipfile
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase, override_settings
from rest_framework.test import APIClient

from archivnik.kartoteka_delete import KartotekaDeleteError, smaz_kartoteku_zakaznika
from archivnik.models import (
    Asset,
    CustomFieldValue,
    Customer,
    Entry,
    Object,
    Reminder,
    Tag,
)
from archivnik.p56a_fixtures import (
    DELETE_EMAIL,
    DELETE_PHONE,
    pridej_asset,
    vytvor_plnou_kartoteku,
    zajisti_booking_se_stejnym_emailem,
)
from archivnik.storage import BunnyUploadError, stored_file_exists
from archivnik.tests import _salon_s_majitelem, _zapni_archivnik
from flow.tests_kartoteka import _flow_ucet, _zapni_archivnik as _zapni_archivnik_flow
from rezervace.models import Rezervace, Zakaznik, Zamestnanec
from salons.models import Salon

REPO_ROOT = Path(__file__).resolve().parents[2]
BANNER = '🔒 Kontaktní údaje jsou pro péči o zákazníka'
BANNER_BODY = (
    'E-mail a telefon používejte pouze v souvislosti s poskytovanou službou. '
    'Archivník není určen pro marketingové rozesílky ani tvorbu marketingových databází. '
    'Za způsob použití údajů odpovídá provozovna jako jejich správce.'
)


def _login(client, email, password='archivnik123'):
    res = client.post(
        '/api/archivnik/auth/login/',
        {'email': email, 'password': password},
        format='json',
    )
    client.credentials(HTTP_X_ARCHIVNIK_TOKEN=res.data['token'])
    return res


@override_settings(BUNNY_STORAGE_ZONE='', BUNNY_STORAGE_API_KEY='', BUNNY_CDN_BASE_URL='')
class P56aCustomerDeleteTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.salon, self.owner = _salon_s_majitelem('P56A A', 'p56a-a@archivnik.test')
        self.salon_b, self.owner_b = _salon_s_majitelem('P56A B', 'p56a-b@archivnik.test')
        _zapni_archivnik(self.salon)
        _zapni_archivnik(self.salon_b)
        _login(self.client, 'p56a-a@archivnik.test')
        self.kept = Customer.objects.create(
            salon=self.salon, jmeno='Anna', prijmeni='Ponechana', email='anna.keep@p56a.test',
        )
        self.foreign = vytvor_plnou_kartoteku(
            self.salon_b, jmeno='Cizi', prijmeni='Tenant', email='cizi@p56a.test',
            telefon='777560099', poznamka='cizi', asset_name='cizi.jpg',
        )
        self.tree = vytvor_plnou_kartoteku(self.salon)
        self.tag = Tag.objects.create(salon=self.salon, nazev='VIP')
        self.tree['customer'].tagy.add(self.tag)
        self.zak, self.rez = zajisti_booking_se_stejnym_emailem(self.salon, DELETE_EMAIL)

    def _delete(self, uuid, potvrzeni, client=None):
        cli = client or self.client
        return cli.delete(
            f'/api/archivnik/customers/{uuid}/',
            {'potvrzeni': potvrzeni},
            format='json',
        )

    def test_majitel_smaze_strom_i_bunny_a_booking_zustane(self):
        c = self.tree['customer']
        asset = self.tree['asset']
        key = asset.storage_key
        self.assertTrue(stored_file_exists(key))
        res = self._delete(c.uuid, c.display_name)
        self.assertEqual(res.status_code, 204, getattr(res, 'data', None))
        self.assertFalse(Customer.objects.filter(pk=c.pk).exists())
        self.assertFalse(Customer.objects.filter(uuid=c.uuid).exists())
        self.assertFalse(Customer.objects.filter(salon=self.salon, email=DELETE_EMAIL).exists())
        self.assertFalse(Customer.objects.filter(salon=self.salon, telefon=DELETE_PHONE).exists())
        self.assertFalse(Object.objects.filter(zakaznik_id=c.id).exists())
        self.assertFalse(CustomFieldValue.objects.filter(objekt__zakaznik_id=c.id).exists())
        self.assertFalse(Entry.objects.filter(zakaznik_id=c.id).exists())
        self.assertFalse(Reminder.objects.filter(zakaznik_id=c.id).exists())
        self.assertFalse(Asset.objects.filter(zakaznik_id=c.id).exists())
        self.assertFalse(stored_file_exists(key))
        self.assertTrue(Customer.objects.filter(pk=self.kept.pk).exists())
        self.assertTrue(Customer.objects.filter(pk=self.foreign['customer'].pk).exists())
        self.assertTrue(stored_file_exists(self.foreign['asset'].storage_key))
        self.assertTrue(Tag.objects.filter(pk=self.tag.pk).exists())
        self.assertTrue(Zakaznik.objects.filter(pk=self.zak.pk).exists())
        self.assertTrue(Rezervace.all_objects.filter(pk=self.rez.pk).exists())
        hledani = self.client.get('/api/archivnik/search/', {'q': DELETE_EMAIL})
        self.assertEqual(hledani.status_code, 200)
        self.assertEqual(hledani.data['zakaznici'], [])

    def test_spatne_potvrzeni_nemaze(self):
        c = self.tree['customer']
        res = self._delete(c.uuid, 'spatne jmeno')
        self.assertEqual(res.status_code, 400)
        self.assertTrue(Customer.objects.filter(pk=c.pk).exists())
        self.assertTrue(stored_file_exists(self.tree['asset'].storage_key))

    def test_zamestnanec_dostane_403(self):
        emp = Zamestnanec.objects.create(
            salon=self.salon,
            jmeno='Zamestnanec',
            role=Zamestnanec.ROLE_ZAMESTNANEC,
            prihlasovaci_jmeno='p56a-emp@archivnik.test',
            aktivni=True,
            zobrazit_na_webu=False,
        )
        emp.set_password('zamestnanec123')
        emp.save(update_fields=['password_hash'])
        emp_client = APIClient()
        login = _login(emp_client, 'p56a-emp@archivnik.test', 'zamestnanec123')
        self.assertEqual(login.status_code, 200)
        self.assertFalse(login.data['je_spravce'])
        c = self.tree['customer']
        res = self._delete(c.uuid, c.display_name, client=emp_client)
        self.assertEqual(res.status_code, 403)
        self.assertTrue(Customer.objects.filter(pk=c.pk).exists())
        self.assertTrue(stored_file_exists(self.tree['asset'].storage_key))

    def test_cizi_tenant_404_a_nesmaze(self):
        foreign = self.foreign['customer']
        res = self._delete(foreign.uuid, foreign.display_name)
        self.assertEqual(res.status_code, 404)
        self.assertTrue(Customer.objects.filter(pk=foreign.pk).exists())
        self.assertTrue(stored_file_exists(self.foreign['asset'].storage_key))

    def test_bunny_failure_neprohlasi_uspech_retry_dokonci(self):
        c = self.tree['customer']
        key = self.tree['asset'].storage_key
        with patch(
            'archivnik.kartoteka_delete.delete_stored_file',
            side_effect=BunnyUploadError('timeout'),
        ):
            with self.assertRaises(KartotekaDeleteError):
                smaz_kartoteku_zakaznika(self.salon, c.uuid)
            res = self._delete(c.uuid, c.display_name)
            self.assertEqual(res.status_code, 409)
        self.assertTrue(Customer.objects.filter(pk=c.pk).exists())
        self.assertTrue(stored_file_exists(key))
        res = self._delete(c.uuid, c.display_name)
        self.assertEqual(res.status_code, 204)
        self.assertFalse(Customer.objects.filter(pk=c.pk).exists())
        self.assertFalse(stored_file_exists(key))

    def test_castecny_bunny_uspech_retry(self):
        c = self.tree['customer']
        druhy = pridej_asset(
            self.salon, c, nazev='dalsi.jpg', objekt=self.tree['objekt'], color=(200, 10, 10),
        )
        first_key = self.tree['asset'].storage_key
        second_key = druhy.storage_key
        real = __import__('archivnik.storage', fromlist=['delete_stored_file']).delete_stored_file

        def boom(key):
            if key == second_key:
                raise BunnyUploadError('timeout')
            return real(key)

        with patch('archivnik.kartoteka_delete.delete_stored_file', side_effect=boom):
            with self.assertRaises(KartotekaDeleteError):
                smaz_kartoteku_zakaznika(self.salon, c.uuid)
        self.assertTrue(Customer.objects.filter(pk=c.pk).exists())
        self.assertFalse(stored_file_exists(first_key))
        self.assertTrue(stored_file_exists(second_key))
        smaz_kartoteku_zakaznika(self.salon, c.uuid)
        self.assertFalse(Customer.objects.filter(pk=c.pk).exists())
        self.assertFalse(stored_file_exists(first_key))
        self.assertFalse(stored_file_exists(second_key))

    def test_smaz_kartoteku_vyzaduje_salon(self):
        c = self.tree['customer']
        with self.assertRaises(KartotekaDeleteError):
            smaz_kartoteku_zakaznika(self.salon_b, c.uuid)
        self.assertTrue(Customer.objects.filter(pk=c.pk).exists())


@override_settings(BUNNY_STORAGE_ZONE='', BUNNY_STORAGE_API_KEY='', BUNNY_CDN_BASE_URL='')
class P56aFlowAfterDeleteTests(TestCase):
    def setUp(self):
        self.http = Client()
        self.salon = Salon.objects.create(name='P56A FLOW', email='p56a-flow@test.local')
        self.owner, _flow = _flow_ucet(self.salon, 'p56a-flow-owner@test.local', 'HesloA123')
        _zapni_archivnik_flow(self.salon)
        self.tree = vytvor_plnou_kartoteku(self.salon)
        self.api = APIClient()
        _login(self.api, 'p56a-flow-owner@test.local', 'HesloA123')

    def test_flow_po_vymazu_nenajde_kartoteku(self):
        c = self.tree['customer']
        login = self.http.post(
            '/api/flow/prihlaseni/',
            data={'email': 'p56a-flow-owner@test.local', 'password': 'HesloA123'},
            content_type='application/json',
        )
        token = login.json()['token']
        before = self.http.get(
            f'/api/flow/kartoteka/zakaznici/{c.uuid}/',
            HTTP_X_FLOW_TOKEN=token,
        )
        self.assertEqual(before.status_code, 200)
        res = self.api.delete(
            f'/api/archivnik/customers/{c.uuid}/',
            {'potvrzeni': c.display_name},
            format='json',
        )
        self.assertEqual(res.status_code, 204)
        after = self.http.get(
            f'/api/flow/kartoteka/zakaznici/{c.uuid}/',
            HTTP_X_FLOW_TOKEN=token,
        )
        self.assertEqual(after.status_code, 404)
        lookup = self.http.get(
            '/api/flow/kartoteka/zakaznici/lookup/',
            {'email': DELETE_EMAIL},
            HTTP_X_FLOW_TOKEN=token,
        )
        self.assertEqual(lookup.json().get('uuid'), None)


@override_settings(BUNNY_STORAGE_ZONE='', BUNNY_STORAGE_API_KEY='', BUNNY_CDN_BASE_URL='')
class P56aExportTests(TestCase):
    def setUp(self):
        self.salon_a, _ = _salon_s_majitelem('Export A', 'export-a@archivnik.test')
        self.salon_b, _ = _salon_s_majitelem('Export B', 'export-b@archivnik.test')
        _zapni_archivnik(self.salon_a)
        _zapni_archivnik(self.salon_b)
        self.a1 = vytvor_plnou_kartoteku(
            self.salon_a, jmeno='Adam', prijmeni='Alfa', email='a1@p56a.test',
            telefon='777560011', asset_name='a1.jpg',
        )
        self.a2 = vytvor_plnou_kartoteku(
            self.salon_a, jmeno='Bára', prijmeni='Beta', email='a2@p56a.test',
            telefon='777560012', asset_name='a2.jpg',
        )
        self.a3 = vytvor_plnou_kartoteku(
            self.salon_a, jmeno='Cyril', prijmeni='Gama', email='a3@p56a.test',
            telefon='777560013', asset_name='a3.jpg',
        )
        self.x = vytvor_plnou_kartoteku(
            self.salon_b, jmeno='Xavier', prijmeni='Cizi', email='x@p56a.test',
            telefon='777560088', asset_name='x-secret.jpg',
        )

    def test_single_export_obsahuje_soubor_a_ne_ciziho(self):
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / 'one.zip'
            call_command(
                'export_archivnik_customer',
                salon_id=self.salon_a.id,
                customer_uuid=str(self.a1['customer'].uuid),
                out=str(out),
                stdout=StringIO(),
            )
            with zipfile.ZipFile(out) as zf:
                names = zf.namelist()
                json_name = next(n for n in names if n.endswith('kartoteka.json'))
                payload = json.loads(zf.read(json_name))
                self.assertEqual(payload['zakaznik']['uuid'], str(self.a1['customer'].uuid))
                self.assertEqual(payload['zakaznik']['email'], 'a1@p56a.test')
                self.assertTrue(payload['objekty'])
                self.assertTrue(payload['zapisy'])
                self.assertTrue(payload['pripominky'])
                self.assertTrue(payload['soubory'])
                self.assertNotIn('storage_key', json.dumps(payload))
                zip_cesta = payload['soubory'][0]['zip_cesta']
                self.assertIn(zip_cesta, names)
                self.assertGreater(len(zf.read(zip_cesta)), 10)
                blob = ' '.join(names) + zf.read(json_name).decode('utf-8')
                self.assertNotIn(str(self.a2['customer'].uuid), blob)
                self.assertNotIn(str(self.x['customer'].uuid), blob)
                self.assertNotIn('x-secret.jpg', blob)
        self.assertTrue(Customer.objects.filter(pk=self.a1['customer'].pk).exists())
        self.assertTrue(stored_file_exists(self.a1['asset'].storage_key))

    def test_single_export_cizi_salon_uuid_selze(self):
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / 'nope.zip'
            with self.assertRaises(CommandError):
                call_command(
                    'export_archivnik_customer',
                    salon_id=self.salon_a.id,
                    customer_uuid=str(self.x['customer'].uuid),
                    out=str(out),
                    stdout=StringIO(),
                )
            self.assertFalse(out.exists())

    def test_partner_exit_je_tenant_scoped_a_nemaze(self):
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / 'exit.zip'
            call_command(
                'export_archivnik_partner',
                salon_id=self.salon_a.id,
                out=str(out),
                stdout=StringIO(),
            )
            with zipfile.ZipFile(out) as zf:
                names = zf.namelist()
                manifest = json.loads(zf.read('manifest.json'))
                uuids = {row['uuid'] for row in manifest['zakaznici']}
                self.assertEqual(
                    uuids,
                    {
                        str(self.a1['customer'].uuid),
                        str(self.a2['customer'].uuid),
                        str(self.a3['customer'].uuid),
                    },
                )
                self.assertNotIn(str(self.x['customer'].uuid), uuids)
                blob = ' '.join(names)
                self.assertNotIn(str(self.x['customer'].uuid), blob)
                self.assertNotIn('x-secret.jpg', blob)
                jpg_files = [n for n in names if n.endswith('.jpg')]
                self.assertGreaterEqual(len(jpg_files), 3)
                for path in jpg_files:
                    self.assertGreater(len(zf.read(path)), 10)
                konfigurace = json.loads(zf.read('konfigurace.json'))
                self.assertTrue(konfigurace['typy_objektu'])
        for tree in (self.a1, self.a2, self.a3, self.x):
            self.assertTrue(Customer.objects.filter(pk=tree['customer'].pk).exists())
            self.assertTrue(stored_file_exists(tree['asset'].storage_key))


class P56aMarketingUiTests(TestCase):
    def test_banner_a_delete_bez_partner_exportu(self):
        arch = (REPO_ROOT / 'archivnik' / 'app.js').read_text(encoding='utf-8')
        flow_js = (REPO_ROOT / 'flow' / 'customer-card.js').read_text(encoding='utf-8')
        flow_html = (REPO_ROOT / 'flow' / 'index.html').read_text(encoding='utf-8')
        self.assertIn(BANNER, arch)
        self.assertIn(BANNER_BODY, arch)
        self.assertIn('Odstranit zákazníka a jeho data', arch)
        self.assertIn('je_spravce', arch)
        self.assertNotIn('export_archivnik', arch)
        self.assertNotIn('Exportovat všechny', arch)
        self.assertNotIn('newsletter', arch.lower())
        self.assertNotIn('.csv', arch)
        self.assertIn(BANNER, flow_js)
        self.assertIn(BANNER, flow_html)
        self.assertNotIn('export_archivnik', flow_js)
        self.assertNotIn('Exportovat', flow_js)
