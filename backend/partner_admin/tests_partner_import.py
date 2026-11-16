from decimal import Decimal

from django.test import TestCase

from partner_admin.models import PotencialniKontakt
from partner_admin.partner_import import (
    ImportNahledZastaralError,
    ImportTokenPouzitError,
    extrahuj_adresni,
    je_placeholder_email,
    najdi_shodu,
    normalizuj_ico,
    normalizuj_radek_partnera,
    normalizuj_souradnice,
    normalizuj_telefon,
    platny_email_pro_import,
    report_podpis,
    rezervuj_token_potvrzeni,
    spust_import,
    spust_import_commit,
    _index_kontaktu,
)


class PartnerImportTests(TestCase):
    def test_gps_nula(self):
        self.assertEqual(normalizuj_souradnice(0, 0), (None, None))

    def test_placeholder_email(self):
        self.assertIsNone(platny_email_pro_import('xxxxx@xxxx.cz'))
        self.assertTrue(je_placeholder_email('xxxxx@xxxx.cz'))

    def test_bez_email_telefon(self):
        data = normalizuj_radek_partnera({
            'company_name': 'Salon',
            'email': None,
            'phone': '+420603842823',
            'ico': '12345678',
        })
        self.assertIsNone(data['email'])
        self.assertEqual(data['_nt_telefon'], '603842823')

    def test_ico_jednoznacne_je_shoda(self):
        PotencialniKontakt.objects.create(jmeno='A', email='a@test.cz', ico='12345678')
        data = {'_nt_email': '', '_nt_telefon': '', '_nt_ico': '12345678'}
        by_email, by_phone, by_ico = _index_kontaktu()
        shoda, pk = najdi_shodu(data, by_email, by_phone, by_ico)
        self.assertEqual(shoda, 'match')
        self.assertIsNotNone(pk)

    def test_ico_na_dvou_kontaktech_je_konflikt(self):
        PotencialniKontakt.objects.create(jmeno='A', email='a@test.cz', ico='12345678')
        PotencialniKontakt.objects.create(jmeno='B', email='b@test.cz', ico='12345678')
        data = {'_nt_email': '', '_nt_telefon': '', '_nt_ico': '12345678'}
        by_email, by_phone, by_ico = _index_kontaktu()
        self.assertEqual(najdi_shodu(data, by_email, by_phone, by_ico)[0], 'ambiguous')

    def test_stejeny_ico_ruzne_provozovny(self):
        PotencialniKontakt.objects.create(jmeno='A', email='a@test.cz', ico='99887766', telefon='603111222')
        PotencialniKontakt.objects.create(jmeno='B', email='b@test.cz', ico='99887766', telefon='603333444')
        data = {'_nt_email': '', '_nt_telefon': '603111222', '_nt_ico': '99887766'}
        by_email, by_phone, by_ico = _index_kontaktu()
        shoda, pk = najdi_shodu(data, by_email, by_phone, by_ico)
        self.assertEqual(shoda, 'match')
        self.assertIsNotNone(pk)

    def test_konflikt_email_telefon(self):
        PotencialniKontakt.objects.create(jmeno='A', email='a@test.cz', telefon='603111222')
        PotencialniKontakt.objects.create(jmeno='B', email='b@test.cz', telefon='603333444')
        data = {'_nt_email': 'a@test.cz', '_nt_telefon': '603333444', '_nt_ico': ''}
        by_email, by_phone, by_ico = _index_kontaktu()
        self.assertEqual(najdi_shodu(data, by_email, by_phone, by_ico)[0], 'ambiguous')

    def test_import_bez_email_vytvori(self):
        report = spust_import(
            [{'company_name': 'Bez mailu', 'phone': '777888999', 'ico': '11111111', 'mesto': 'Opava'}],
            dry_run=False,
        )
        self.assertEqual(report.vytvoreno, 1)
        self.assertIsNone(PotencialniKontakt.objects.get(ico='11111111').email)

    def test_import_doplni_pouze_nova_pole(self):
        kontakt = PotencialniKontakt.objects.create(
            jmeno='Firma', email='x@test.cz', stav=PotencialniKontakt.STAV_EMAIL, poznamka='Zachovat',
        )
        pred_stav = kontakt.stav
        spust_import(
            [{'company_name': 'Firma', 'email': 'x@test.cz', 'mesto': 'Ostrava'}],
            dry_run=False,
        )
        kontakt.refresh_from_db()
        self.assertEqual(kontakt.mesto, 'Ostrava')
        self.assertEqual(kontakt.stav, pred_stav)
        self.assertEqual(kontakt.poznamka, 'Zachovat')

    def test_opakovany_import_idempotentni(self):
        payloads = [{'company_name': 'Nový', 'email': 'idem@test.cz', 'mesto': 'Praha'}]
        r1 = spust_import(payloads, dry_run=False)
        pocet = PotencialniKontakt.objects.count()
        r2 = spust_import(payloads, dry_run=False)
        self.assertEqual(PotencialniKontakt.objects.count(), pocet)
        self.assertEqual(r2.vytvoreno, 0)
        self.assertEqual(r2.preskoceno, 1)
        self.assertEqual(r2.aktualizovano, 0)
        self.assertEqual(r1.vytvoreno, 1)

    def test_extrahuj_adresni_alias(self):
        d = extrahuj_adresni({'city': 'Liberec', 'lat': 0, 'lon': 0})
        self.assertEqual(d['mesto'], 'Liberec')
        self.assertIsNone(d['latitude'])

    def test_vyplnene_pole_stav_a_poznamka_zustanou(self):
        kontakt = PotencialniKontakt.objects.create(
            jmeno='Firma', email='x@test.cz', stav=PotencialniKontakt.STAV_EMAIL,
            poznamka='Zachovat', mesto='Brno', adresa='Stará 1', telefon='777111222',
        )
        puvodni_id = kontakt.pk
        report = spust_import([{
            'company_name': 'Jiné jméno',
            'email': 'x@test.cz',
            'phone': '777111222',
            'mesto': 'Ostrava',
            'adresa': 'Nová 2',
            'cast_obce': 'Poruba',
            'status': 'prodano',
            'description': 'Text z JSON',
        }], dry_run=False)
        kontakt.refresh_from_db()
        self.assertEqual(kontakt.pk, puvodni_id)
        self.assertEqual(kontakt.jmeno, 'Firma')
        self.assertEqual(kontakt.mesto, 'Brno')
        self.assertEqual(kontakt.adresa, 'Stará 1')
        self.assertEqual(kontakt.cast_obce, 'Poruba')
        self.assertEqual(kontakt.stav, PotencialniKontakt.STAV_EMAIL)
        self.assertEqual(kontakt.poznamka, 'Zachovat')
        self.assertEqual(report.aktualizovano, 1)
        self.assertEqual(report.statusy_zmeneny, [])

    def test_neshodny_telefon_se_neslucuje(self):
        PotencialniKontakt.objects.create(
            jmeno='A', email='a@test.cz', telefon='111222333', ico='11111111',
        )
        report = spust_import([{
            'company_name': 'B',
            'email': 'a@test.cz',
            'phone': '444555666',
            'ico': '22222222',
            'mesto': 'Praha',
        }], dry_run=False)
        self.assertEqual(report.vytvoreno, 0)
        self.assertEqual(report.nejednoznacne, 1)
        self.assertEqual(PotencialniKontakt.objects.count(), 1)
        self.assertIsNone(PotencialniKontakt.objects.get().mesto)

    def test_dry_run_nezapise(self):
        report = spust_import(
            [{'company_name': 'Nový', 'email': 'dry@test.cz', 'mesto': 'Olomouc'}],
            dry_run=True,
        )
        self.assertEqual(report.vytvoreno, 1)
        self.assertEqual(PotencialniKontakt.objects.count(), 0)

    def test_placeholder_telefon_neslepi_dva_subjekty(self):
        report = spust_import([
            {'company_name': 'A', 'email': 'xxxxx@xxxx.cz', 'phone': '111111111', 'ico': '11111111', 'mesto': 'A'},
            {'company_name': 'B', 'email': 'xxxxx@xxxx.cz', 'phone': '111 111 111', 'ico': '22222222', 'mesto': 'B'},
        ], dry_run=False)
        self.assertEqual(report.vytvoreno, 2)
        self.assertEqual(PotencialniKontakt.objects.count(), 2)

    def test_duplicitni_telefon_v_json_je_konflikt(self):
        report = spust_import([
            {'company_name': 'Salon A', 'email': 'a-telefon-dup@test.cz', 'phone': '+420 777 111 222'},
            {'company_name': 'Salon B', 'email': 'b-telefon-dup@test.cz', 'phone': '777111222'},
        ], dry_run=False)
        self.assertEqual(report.vytvoreno, 1)
        self.assertEqual(report.nejednoznacne, 1)
        self.assertEqual(PotencialniKontakt.objects.count(), 1)

    def test_duplicitni_telefon_v_json_bez_shody_je_konflikt(self):
        report = spust_import([
            {'company_name': 'Salon C', 'phone': '603111222', 'ico': '11111111'},
            {'company_name': 'Salon D', 'phone': '603111222', 'ico': '22222222'},
        ], dry_run=False)
        self.assertEqual(report.vytvoreno, 1)
        self.assertEqual(report.nejednoznacne, 1)
        self.assertEqual(report.duplicitni_vstup, 1)

    def test_stejeny_telefon_dvakrat_update_kontaktu(self):
        PotencialniKontakt.objects.create(
            jmeno='Salon', email='dup-row@test.cz', telefon='777 333 444', stav=PotencialniKontakt.STAV_EMAIL,
        )
        report = spust_import([
            {'company_name': 'Salon', 'email': 'dup-row@test.cz', 'phone': '777333444', 'mesto': 'Praha'},
            {'company_name': 'Salon', 'email': 'dup-row@test.cz', 'phone': '+420777333444', 'mesto': 'Praha'},
        ], dry_run=False)
        self.assertEqual(report.vytvoreno, 0)
        self.assertEqual(report.aktualizovano, 1)
        self.assertEqual(report.preskoceno, 1)
        self.assertEqual(report.nejednoznacne, 0)

    def test_commit_podpis_kontrola(self):
        payloads = [{'company_name': 'X', 'email': 'podpis@test.cz', 'phone': '777444555', 'mesto': 'Olomouc'}]
        nahled = spust_import(payloads, dry_run=True)
        podpis = report_podpis(nahled)
        report = spust_import_commit(payloads, ulozeny_podpis=podpis)
        self.assertEqual(report.vytvoreno, 1)
        with self.assertRaises(ImportNahledZastaralError):
            spust_import_commit(payloads, ulozeny_podpis=podpis)

    def test_token_potvrzeni_jen_jednou(self):
        rezervuj_token_potvrzeni('test-token-abc')
        with self.assertRaises(ImportTokenPouzitError):
            rezervuj_token_potvrzeni('test-token-abc')