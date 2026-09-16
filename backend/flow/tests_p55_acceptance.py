"""P5.5 — reprodukovatelná acceptance sada, scoped wipe, integrita, legacy freeze."""
from __future__ import annotations

from io import StringIO

from django.core.management import call_command
from django.test import Client, TestCase
from django.utils import timezone

from archivnik.models import (
    CustomFieldDef,
    Customer,
    Entry,
    Obor,
    Object,
    ObjectType,
    Reminder,
    Stav,
)
from flow.customer_card_models import CustomerCard, CustomerVisit
from flow.kartoteka_services import attach_archivnik_customer_links
from flow.models import FlowUser
from flow.p55_acceptance import (
    EMAIL_A,
    EMAIL_B,
    EMAIL_C,
    EMAIL_D,
    EMAIL_F,
    NOTE_PREFIX,
    P53_EMAIL_SUFFIX,
    P53_NOTE_PREFIX,
    TAG,
    integrity_report,
    seed_acceptance,
    wipe_p53,
    wipe_salon_kartoteka,
    wipe_tagged,
)
from flow.tests_kartoteka import _flow_ucet, _zapni_archivnik
from partner_admin.models import MODUL_ARCHIVNIK, PartnerModul
from rezervace.models import Rezervace, Zamestnanec
from salons.models import CenikPolozka, Salon


class P55AcceptanceSeedTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.salon_a = Salon.objects.create(name='P55 A', email='p55-a@test.local')
        self.salon_b = Salon.objects.create(name='P55 B', email='p55-b@test.local')
        self.owner_a, self.flow_a = _flow_ucet(
            self.salon_a, 'p55-owner-a@test.local', 'HesloA123', jmeno='Majitel A',
        )
        self.owner_b, self.flow_b = _flow_ucet(
            self.salon_b, 'p55-owner-b@test.local', 'HesloB123', jmeno='Majitel B',
        )
        _zapni_archivnik(self.salon_a)
        _zapni_archivnik(self.salon_b)
        self.obor_a = Obor.objects.create(
            salon=self.salon_a, nazev='Beauty', poradi=1, zdroj_preset='beauty', aktualni=True,
        )
        self.typ_vlasy = ObjectType.objects.create(
            salon=self.salon_a, obor=self.obor_a, nazev='Vlasy', vyzaduje_nazev=True, poradi=1,
        )
        self.typ_vousy = ObjectType.objects.create(
            salon=self.salon_a, obor=self.obor_a, nazev='Vousy', vyzaduje_nazev=True, poradi=2,
        )
        CustomFieldDef.objects.create(
            salon=self.salon_a, typ=self.typ_vlasy, nazev='Typ vlasů', druh='text', poradi=1,
        )
        ObjectType.objects.create(salon=self.salon_b, nazev='Pes', vyzaduje_nazev=True)
        CenikPolozka.objects.create(
            salon=self.salon_a, nazev='Střih', cena=500, delka_minut=45, aktivni=True,
        )
        Zamestnanec.objects.create(
            salon=self.salon_a, jmeno='Markéta', role='zamestnanec', aktivni=True, poradi=1,
        )
        self.boris = Customer.objects.create(
            salon=self.salon_b, jmeno='Boris', prijmeni='Cizí', email='boris@other.test',
        )

    def _login(self, email, password):
        r = self.client.post(
            '/api/flow/prihlaseni/',
            data={'email': email, 'password': password},
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 200)
        return r.json()['token']

    def test_seed_vytvori_scenare_a_ne_legacy(self):
        legacy_before = CustomerCard.objects.count()
        created = seed_acceptance(self.salon_a)
        self.assertEqual(created['jan'].email, EMAIL_A)
        self.assertEqual(created['petr'].email, EMAIL_B)
        self.assertEqual(created['anna'].stav, Stav.ARCHIVOVANY)
        self.assertEqual(created['karel'].email, EMAIL_D)
        self.assertEqual(created['walkin'].email, '')
        self.assertEqual(created['walkin'].poznamka[:4], NOTE_PREFIX)
        self.assertEqual(Object.objects.filter(zakaznik=created['jan']).count(), 2)
        self.assertTrue(Entry.objects.filter(zakaznik=created['petr'], objekt__isnull=True).exists())
        overdue = Reminder.objects.get(zakaznik=created['karel'])
        self.assertLess(overdue.termin, timezone.localdate())
        self.assertEqual(Customer.objects.filter(salon=self.salon_a, email=EMAIL_A).count(), 1)
        self.assertEqual(CustomerCard.objects.count(), legacy_before)
        self.assertEqual(CustomerVisit.objects.count(), 0)
        self.assertEqual(
            PartnerModul.objects.filter(salon=self.salon_a, modul__kod=MODUL_ARCHIVNIK).count(),
            1,
        )

    def test_opakované_spusteni_bez_reset_neduplikuje(self):
        call_command('seed_p55_acceptance', salon_id=self.salon_a.id, stdout=StringIO())
        call_command('seed_p55_acceptance', salon_id=self.salon_a.id, stdout=StringIO())
        self.assertEqual(Customer.objects.filter(salon=self.salon_a, email=EMAIL_A).count(), 1)
        self.assertEqual(Customer.objects.filter(salon=self.salon_a, poznamka__startswith=NOTE_PREFIX).count(), 5)
        self.assertEqual(Rezervace.objects.filter(salon=self.salon_a, poznamka_interni=TAG).count(), 3)

    def test_reset_je_idempotentni(self):
        seed_acceptance(self.salon_a)
        first_uuid = Customer.objects.get(salon=self.salon_a, email=EMAIL_A).uuid
        call_command('seed_p55_acceptance', salon_id=self.salon_a.id, reset=True, stdout=StringIO())
        self.assertEqual(Customer.objects.filter(salon=self.salon_a, email=EMAIL_A).count(), 1)
        self.assertNotEqual(Customer.objects.get(salon=self.salon_a, email=EMAIL_A).uuid, first_uuid)
        self.assertEqual(Rezervace.objects.filter(salon=self.salon_a, poznamka_interni=TAG).count(), 3)

    def test_cleanup_salon_nemaže_p3_p4_konfiguraci(self):
        seed_acceptance(self.salon_a)
        types_before = ObjectType.objects.filter(salon=self.salon_a).count()
        fields_before = CustomFieldDef.objects.filter(salon=self.salon_a).count()
        obory_before = Obor.objects.filter(salon=self.salon_a).count()
        flow_before = FlowUser.objects.filter(salon=self.salon_a).count()
        modul_before = PartnerModul.objects.filter(salon=self.salon_a).count()
        wipe_salon_kartoteka(self.salon_a)
        self.assertEqual(Customer.objects.filter(salon=self.salon_a).count(), 0)
        self.assertEqual(ObjectType.objects.filter(salon=self.salon_a).count(), types_before)
        self.assertEqual(CustomFieldDef.objects.filter(salon=self.salon_a).count(), fields_before)
        self.assertEqual(Obor.objects.filter(salon=self.salon_a).count(), obory_before)
        self.assertEqual(FlowUser.objects.filter(salon=self.salon_a).count(), flow_before)
        self.assertEqual(PartnerModul.objects.filter(salon=self.salon_a).count(), modul_before)
        self.assertTrue(Customer.objects.filter(pk=self.boris.pk).exists())

    def test_cleanup_p53_nesaha_na_p55(self):
        seed_acceptance(self.salon_a)
        Customer.objects.create(
            salon=self.salon_a, jmeno='Jana', prijmeni='P53',
            email=f'jana.existujici{P53_EMAIL_SUFFIX}',
            poznamka=f'{P53_NOTE_PREFIX} leftover',
        )
        wipe_p53(self.salon_a)
        self.assertFalse(
            Customer.objects.filter(salon=self.salon_a, email__iendswith=P53_EMAIL_SUFFIX).exists()
        )
        self.assertTrue(Customer.objects.filter(salon=self.salon_a, email=EMAIL_A).exists())

    def test_tenant_b_neovlivni_sadu_a(self):
        seed_acceptance(self.salon_a)
        token_b = self._login('p55-owner-b@test.local', 'HesloB123')
        jan = Customer.objects.get(salon=self.salon_a, email=EMAIL_A)
        r = self.client.get(
            f'/api/flow/kartoteka/zakaznici/{jan.uuid}/',
            HTTP_X_FLOW_TOKEN=token_b,
        )
        self.assertEqual(r.status_code, 404)
        obj = Object.objects.filter(zakaznik=jan).first()
        entry = Entry.objects.filter(zakaznik=jan).first()
        rem = Reminder.objects.filter(zakaznik=jan).first()
        token_a = self._login('p55-owner-a@test.local', 'HesloA123')
        deny = self.client.get(
            f'/api/flow/kartoteka/zakaznici/{self.boris.uuid}/',
            HTTP_X_FLOW_TOKEN=token_a,
        )
        self.assertEqual(deny.status_code, 404)
        self.assertNotEqual(obj.salon_id, self.salon_b.id)
        self.assertNotEqual(entry.salon_id, self.salon_b.id)
        self.assertNotEqual(rem.salon_id, self.salon_b.id)
        report = integrity_report(self.salon_a, extra_salon=self.salon_b)
        self.assertEqual(report['illegal'], 0)
        self.assertEqual(report['extra_salon']['shared_customer_uuids'], 0)

    def test_flow_me_archivnik_active(self):
        seed_acceptance(self.salon_a)
        token = self._login('p55-owner-a@test.local', 'HesloA123')
        r = self.client.get('/api/flow/me/', HTTP_X_FLOW_TOKEN=token)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['archivnik_active'])

    def test_kalendar_match_f_g_h(self):
        created = seed_acceptance(self.salon_a)
        items = [
            {
                'id': created['rez_g'].id,
                'kontaktni_email': EMAIL_A,
                'kontaktni_jmeno': 'P55 Jan Novák',
            },
            {
                'id': created['rez_f'].id,
                'kontaktni_email': EMAIL_F,
                'kontaktni_jmeno': 'P55 Nový Host',
            },
            {
                'id': created['rez_h'].id,
                'kontaktni_email': '',
                'kontaktni_jmeno': 'P55 Bez E-mailu',
            },
        ]
        attach_archivnik_customer_links(self.salon_a.id, items)
        self.assertEqual(items[0]['archivnik_customer_uuid'], str(created['jan'].uuid))
        self.assertIsNone(items[1]['archivnik_customer_uuid'])
        self.assertIsNone(items[2]['archivnik_customer_uuid'])
        self.assertFalse(
            Customer.objects.filter(salon=self.salon_a, email=EMAIL_F).exists()
        )

    def test_walkin_bez_emailu_se_nemačuje_na_rezervaci(self):
        created = seed_acceptance(self.salon_a)
        items = [{'id': created['rez_h'].id, 'kontaktni_email': '', 'kontaktni_jmeno': 'Eliška Bezmail'}]
        attach_archivnik_customer_links(self.salon_a.id, items)
        self.assertIsNone(items[0]['archivnik_customer_uuid'])
        self.assertEqual(created['walkin'].email, '')

    def test_zapis_object_create_nepíše_legacy(self):
        created = seed_acceptance(self.salon_a)
        token = self._login('p55-owner-a@test.local', 'HesloA123')
        before = CustomerCard.objects.count()
        r = self.client.post(
            f'/api/flow/kartoteka/zakaznici/{created["jan"].uuid}/objekty/',
            data={'typ_uuid': str(self.typ_vousy.uuid), 'nazev': 'P5.5 nový objekt'},
            content_type='application/json',
            HTTP_X_FLOW_TOKEN=token,
        )
        self.assertEqual(r.status_code, 201)
        e = self.client.post(
            f'/api/flow/kartoteka/zakaznici/{created["jan"].uuid}/zapisy/',
            data={'text': 'P5.5 nový zápis z testu'},
            content_type='application/json',
            HTTP_X_FLOW_TOKEN=token,
        )
        self.assertEqual(e.status_code, 201)
        self.assertEqual(CustomerCard.objects.count(), before)
        self.assertEqual(CustomerVisit.objects.count(), 0)

    def test_cleanup_salon_nemaže_data_salonu_b(self):
        seed_acceptance(self.salon_a)
        wipe_salon_kartoteka(self.salon_a)
        self.assertTrue(Customer.objects.filter(pk=self.boris.pk).exists())

    def test_archivovany_je_read_only_ve_flow(self):
        created = seed_acceptance(self.salon_a)
        token = self._login('p55-owner-a@test.local', 'HesloA123')
        r = self.client.post(
            f'/api/flow/kartoteka/zakaznici/{created["anna"].uuid}/zapisy/',
            data={'text': 'nesmí projít'},
            content_type='application/json',
            HTTP_X_FLOW_TOKEN=token,
        )
        self.assertEqual(r.status_code, 409)
        detail = self.client.get(
            f'/api/flow/kartoteka/zakaznici/{created["anna"].uuid}/',
            HTTP_X_FLOW_TOKEN=token,
        )
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()['stav'], 'archivovany')

    def test_integrity_command_pass(self):
        seed_acceptance(self.salon_a)
        out = StringIO()
        call_command(
            'check_p55_integrity',
            salon_id=self.salon_a.id,
            extra_salon_id=self.salon_b.id,
            stdout=out,
        )
        self.assertIn('P5.5 integrity PASS', out.getvalue())

    def test_wipe_tagged_nesaha_na_cizi_poznamku(self):
        seed_acceptance(self.salon_a)
        other = Customer.objects.create(
            salon=self.salon_a, jmeno='Jiný', prijmeni='Klient',
            email='jiny@example.test', poznamka='ostrá poznámka',
        )
        wipe_tagged(self.salon_a)
        self.assertTrue(Customer.objects.filter(pk=other.pk).exists())
        self.assertFalse(Customer.objects.filter(salon=self.salon_a, email=EMAIL_A).exists())
        self.assertEqual(Customer.objects.filter(salon=self.salon_a, email=EMAIL_C).count(), 0)
        self.assertEqual(Customer.objects.filter(salon=self.salon_a, email=EMAIL_B).count(), 0)
        self.assertEqual(Customer.objects.filter(salon=self.salon_a, email=EMAIL_D).count(), 0)
