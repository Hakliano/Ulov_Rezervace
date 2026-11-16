from decimal import Decimal

from django.test import TestCase

from partner_admin.models import PotencialniKontakt
from partner_admin.partner_import import (
    extrahuj_adresni,
    je_placeholder_email,
    najdi_shodu,
    normalizuj_ico,
    normalizuj_radek_partnera,
    normalizuj_souradnice,
    normalizuj_telefon,
    platny_email_pro_import,
    spust_import,
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

    def test_ico_samo_ambiguous(self):
        PotencialniKontakt.objects.create(jmeno='A', email='a@test.cz', ico='12345678')
        data = {'_nt_email': '', '_nt_telefon': '', '_nt_ico': '12345678'}
        by_email, by_phone, by_ico = _index_kontaktu()
        shoda, _ = najdi_shodu(data, by_email, by_phone, by_ico)
        self.assertEqual(shoda, 'ambiguous')

    def test_stejeny_ico_ruzne_provozovny(self):
        PotencialniKontakt.objects.create(jmeno='A', email='a@test.cz', ico='99887766', telefon='111111111')
        PotencialniKontakt.objects.create(jmeno='B', email='b@test.cz', ico='99887766', telefon='222222222')
        data = {'_nt_email': '', '_nt_telefon': '111111111', '_nt_ico': '99887766'}
        by_email, by_phone, by_ico = _index_kontaktu()
        shoda, pk = najdi_shodu(data, by_email, by_phone, by_ico)
        self.assertEqual(shoda, 'match')
        self.assertIsNotNone(pk)

    def test_konflikt_email_telefon(self):
        PotencialniKontakt.objects.create(jmeno='A', email='a@test.cz', telefon='111111111')
        PotencialniKontakt.objects.create(jmeno='B', email='b@test.cz', telefon='222222222')
        data = {'_nt_email': 'a@test.cz', '_nt_telefon': '222222222', '_nt_ico': ''}
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
        self.assertEqual(r1.vytvoreno, 1)

    def test_extrahuj_adresni_alias(self):
        d = extrahuj_adresni({'city': 'Liberec', 'lat': 0, 'lon': 0})
        self.assertEqual(d['mesto'], 'Liberec')
        self.assertIsNone(d['latitude'])