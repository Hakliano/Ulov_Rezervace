from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from rezervace.models import SalonAuditLog, Zamestnanec, ZamestnanecSession
from salons.models import Salon

from .models import HromadnyEmail, PartnerNastaveni, PartnerTarif, PlatbaPartnera, TechnickaChyba, UpozorneniPlatby
from .services import posun_splatnost


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class PartnerAdminTests(TestCase):
    def setUp(self):
        self.salon = Salon.objects.create(
            name='Test Salon',
            email='majitel@example.test',
        )
        self.partner = self.salon.partner_nastaveni
        self.partner.fakturacni_email = 'platby@example.test'
        self.partner.variabilni_symbol = '9000000001'
        self.partner.castka = Decimal('499.00')
        self.partner.dalsi_splatnost = date(2026, 1, 31)
        self.partner.save()
        self.superuser = get_user_model().objects.create_superuser(
            username='superadmin',
            email='admin@example.test',
            password='bezpecne-test-heslo',
        )
        self.majitel = Zamestnanec.objects.create(
            salon=self.salon,
            jmeno='Majitelka',
            role=Zamestnanec.ROLE_MAJITEL,
            prihlasovaci_jmeno='majitelka',
            aktivni=True,
        )
        self.majitel.set_password('puvodni-heslo')
        self.majitel.save()

    def test_dashboard_vyzaduje_superadmina(self):
        response = self.client.get(reverse('partner_admin:dashboard'))
        self.assertEqual(response.status_code, 302)

        normal_user = get_user_model().objects.create_user(username='normal', password='heslo-12345')
        self.client.force_login(normal_user)
        response = self.client.get(reverse('partner_admin:dashboard'))
        self.assertEqual(response.status_code, 302)

        self.client.force_login(self.superuser)
        response = self.client.get(reverse('partner_admin:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Salon')
        self.assertContains(response, 'sidebar-brand')
        self.assertContains(response, 'global-search')
        self.assertContains(response, 'New%20Project.webp')
        self.assertContains(response, 'Superadmin')
        self.assertContains(response, 'Přijato tento měsíc')

        seznam = self.client.get(reverse('partner_admin:partneri'))
        self.assertEqual(seznam.status_code, 200)
        self.assertContains(seznam, 'Test Salon')

    def test_block_je_rucni_a_api_vraci_423(self):
        jiny_salon = Salon.objects.create(name='Jiný salon', email='jiny@example.test')
        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse('partner_admin:blokovat', args=[self.salon.id]),
            {'potvrzeni': 'BLOCK', 'duvod': 'Test'},
        )
        self.assertEqual(response.status_code, 302)
        self.partner.refresh_from_db()
        self.assertEqual(self.partner.stav, PartnerNastaveni.STAV_BLOCKED)

        self.client.logout()
        response = self.client.get(f'/api/salon/{self.salon.id}/')
        self.assertEqual(response.status_code, 423)
        self.assertEqual(response.json()['kod'], 'salon_blocked')
        response = self.client.get(f'/api/salon/{jiny_salon.id}/')
        self.assertEqual(response.status_code, 200)

    def test_potvrzeni_platby_posune_splatnost_a_neblokuje(self):
        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse('partner_admin:potvrdit_platbu', args=[self.salon.id]),
            {
                'zaplaceno_dne': '2026-02-02',
                'prijata_castka': '499.00',
                'poznamka': 'Spárováno ručně',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.partner.refresh_from_db()
        self.assertEqual(self.partner.dalsi_splatnost, date(2026, 2, 28))
        self.assertEqual(self.partner.stav, PartnerNastaveni.STAV_ACTIVE)
        self.assertTrue(
            PlatbaPartnera.objects.filter(
                salon=self.salon,
                splatnost=date(2026, 1, 31),
                zaplaceno_dne=date(2026, 2, 2),
            ).exists()
        )

    def test_reset_hesla_zrusi_stare_relace(self):
        ZamestnanecSession.objects.create(
            zamestnanec=self.majitel,
            expirace='2030-01-01T00:00:00Z',
        )
        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse('partner_admin:reset_hesla', args=[self.salon.id, self.majitel.id]),
            {'nove_heslo': 'nove-bezpecne-heslo'},
        )
        self.assertEqual(response.status_code, 302)
        self.majitel.refresh_from_db()
        self.assertTrue(self.majitel.check_password('nove-bezpecne-heslo'))
        self.assertFalse(self.majitel.sessiony.exists())
        self.assertTrue(SalonAuditLog.objects.filter(salon=self.salon, kategorie='ucty').exists())

    def test_rucni_upozorneni_se_zaloguje(self):
        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse('partner_admin:odeslat_upozorneni', args=[self.salon.id]),
            {
                'predmet': 'Vlastní předmět upozornění',
                'text': 'Vlastní text upozornění.',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['platby@example.test'])
        self.assertTrue(
            UpozorneniPlatby.objects.filter(
                salon=self.salon,
                uspesne=True,
                predmet='Vlastní předmět upozornění',
                text='Vlastní text upozornění.',
            ).exists()
        )
        self.partner.refresh_from_db()
        self.assertEqual(self.partner.stav, PartnerNastaveni.STAV_ACTIVE)

    def test_posun_splatnosti_resi_konec_mesice(self):
        self.assertEqual(
            posun_splatnost(date(2026, 1, 31), PartnerNastaveni.PERIODA_MESIC),
            date(2026, 2, 28),
        )

    def test_vlastni_domena_musi_byt_jedinecna(self):
        self.partner.domena = 'salon.example.test'
        self.partner.save()
        jiny_salon = Salon.objects.create(name='Jiný salon')
        jine_nastaveni = jiny_salon.partner_nastaveni
        jine_nastaveni.domena = 'salon.example.test'
        with self.assertRaises(ValidationError):
            jine_nastaveni.save()

    def test_dni_po_splatnosti_a_filtry(self):
        self.partner.dalsi_splatnost = date(2026, 1, 1)
        self.partner.save()
        self.assertEqual(self.partner.dni_po_splatnosti, (date.today() - date(2026, 1, 1)).days)

        bez_vs = Salon.objects.create(name='Bez VS', email='bezvs@example.test')
        partner_bez_vs = bez_vs.partner_nastaveni
        partner_bez_vs.variabilni_symbol = None
        partner_bez_vs.save()

        self.client.force_login(self.superuser)
        response = self.client.get(reverse('partner_admin:partneri'), {'platba': 'po_splatnosti'})
        self.assertContains(response, 'Test Salon')
        self.assertContains(response, f'+{self.partner.dni_po_splatnosti} dní')

        response = self.client.get(reverse('partner_admin:partneri'), {'platba': 'bez_vs'})
        self.assertContains(response, 'Bez VS')
        self.assertNotContains(response, 'Test Salon')

        response = self.client.get(reverse('partner_admin:partneri'), {'stav': 'active'})
        self.assertContains(response, 'Test Salon')

    def test_export_csv_respektuje_filtry(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse('partner_admin:export_csv'), {'stav': 'active'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')
        content = response.content.decode('utf-8-sig')
        self.assertIn('Test Salon', content)
        self.assertIn('9000000001', content)
        self.assertIn('Další splatnost', content)

    def test_detail_ma_sablony_upozorneni(self):
        self.client.force_login(self.superuser)
        response = self.client.get(
            reverse('partner_admin:detail', args=[self.salon.id]),
            {'tab': 'upozorneni'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '1. upomínka')
        self.assertContains(response, '2. upomínka')
        self.assertContains(response, 'Před blokací')
        self.assertContains(response, 'upozorneni-sablony')

    def test_export_platby_salonu(self):
        PlatbaPartnera.objects.create(
            salon=self.salon,
            splatnost=date(2025, 12, 31),
            zaplaceno_dne=date(2026, 1, 2),
            ocekavana_castka=Decimal('499.00'),
            prijata_castka=Decimal('499.00'),
            variabilni_symbol='9000000001',
            poznamka='Test export',
            oznacil=self.superuser,
        )
        self.client.force_login(self.superuser)
        response = self.client.get(reverse('partner_admin:export_platby_csv', args=[self.salon.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')
        content = response.content.decode('utf-8-sig')
        self.assertIn('Test Salon', content)
        self.assertIn('ZAPLACENO', content)
        self.assertIn('31.12.2025', content)
        self.assertIn('9000000001', content)
        self.assertIn('Test export', content)

    def test_ulozeni_castky_nesmaze_splatnost(self):
        """DateInput musí posílat YYYY-MM-DD, jinak prohlížeč pole vyprázdní."""
        self.client.force_login(self.superuser)
        detail = self.client.get(reverse('partner_admin:detail', args=[self.salon.id]))
        html = detail.content.decode()
        self.assertIn('value="2026-01-31"', html)

        response = self.client.post(
            reverse('partner_admin:ulozit_nastaveni', args=[self.salon.id]),
            {
                'domena': '',
                'tarif': 'Partner pro váš salon',
                'fakturacni_email': 'platby@example.test',
                'variabilni_symbol': '9000000001',
                'periodicita': PartnerNastaveni.PERIODA_MESIC,
                'castka': '1.00',
                'dalsi_splatnost': '2026-01-31',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.partner.refresh_from_db()
        self.assertEqual(self.partner.castka, Decimal('1.00'))
        self.assertEqual(self.partner.dalsi_splatnost, date(2026, 1, 31))

    def test_ulozeni_nastaveni_vrati_hodnoty_do_formulare(self):
        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse('partner_admin:ulozit_nastaveni', args=[self.salon.id]),
            {
                'domena': 'kudrlinka-test.cz',
                'tarif': 'Partnerství Kudrlinka',
                'fakturacni_email': 'fakturace@kudrlinka-test.cz',
                'variabilni_symbol': '1900000019',
                'periodicita': PartnerNastaveni.PERIODA_MESIC,
                'castka': '499,00',
                'dalsi_splatnost': '2026-09-01',
                'ulov_cislo_uctu': '123456789/0100',
                'tab': 'partner',
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.partner.refresh_from_db()
        self.assertEqual(self.partner.domena, 'kudrlinka-test.cz')
        self.assertEqual(self.partner.tarif, 'Partnerství Kudrlinka')
        self.assertEqual(self.partner.fakturacni_email, 'fakturace@kudrlinka-test.cz')
        self.assertEqual(self.partner.variabilni_symbol, '1900000019')
        self.assertEqual(self.partner.castka, Decimal('499.00'))
        self.assertEqual(self.partner.dalsi_splatnost, date(2026, 9, 1))
        self.assertEqual(self.partner.ulov_cislo_uctu, '123456789/0100')
        html = response.content.decode()
        self.assertIn('Nastavení partnera bylo uloženo.', html)
        self.assertIn('tarif: Partnerství Kudrlinka', html)
        self.assertIn('value="Partnerství Kudrlinka"', html)
        self.assertIn('value="fakturace@kudrlinka-test.cz"', html)
        self.assertIn('value="1900000019"', html)
        self.assertIn('value="2026-09-01"', html)
        self.assertIn('<dt>Tarif</dt>', html)
        self.assertIn('Partnerství Kudrlinka', html)

    def test_neplatny_vs_ponecha_vyplneny_tarif(self):
        self.client.force_login(self.superuser)
        puvodni_tarif = self.partner.tarif
        response = self.client.post(
            reverse('partner_admin:ulozit_nastaveni', args=[self.salon.id]),
            {
                'domena': 'kudrlinka-test.cz',
                'tarif': 'Nový tarif který se nesmí ztratit',
                'fakturacni_email': 'fakturace@kudrlinka-test.cz',
                'variabilni_symbol': 'abc',
                'periodicita': PartnerNastaveni.PERIODA_MESIC,
                'castka': '499.00',
                'dalsi_splatnost': '2026-09-01',
                'tab': 'partner',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.partner.refresh_from_db()
        self.assertEqual(self.partner.tarif, puvodni_tarif)
        html = response.content.decode()
        self.assertIn('Nový tarif který se nesmí ztratit', html)
        self.assertIn('Variabilní symbol musí obsahovat 1 až 10 číslic.', html)
        self.assertNotIn('Nastavení partnera bylo uloženo.', html)

    def test_novy_partner_vytvori_salon_majitele_a_flow(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse('partner_admin:novy'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Nový partner')

        response = self.client.post(
            reverse('partner_admin:novy'),
            {
                'name': 'AutoServis Test',
                'address': 'Dílenska 1',
                'phone': '+420777000111',
                'email': 'info@autoservis-test.cz',
                'majitel_email': 'majitel@autoservis-test.cz',
                'majitel_heslo': 'DocasneHeslo99',
                'aktivovat_flow': 'on',
                'domena': 'autoservis-test.cz',
                'tarif': 'Partner pro vaši provozovnu',
                'fakturacni_email': 'fakturace@autoservis-test.cz',
                'variabilni_symbol': '88001234',
                'periodicita': PartnerNastaveni.PERIODA_MESIC,
                'castka': '499.00',
                'dalsi_splatnost': '',
                'ulov_cislo_uctu': '',
            },
        )
        self.assertEqual(response.status_code, 302)
        salon = Salon.objects.get(name='AutoServis Test')
        self.assertEqual(salon.email, 'info@autoservis-test.cz')
        partner = salon.partner_nastaveni
        self.assertEqual(partner.variabilni_symbol, '88001234')
        self.assertEqual(partner.domena, 'autoservis-test.cz')
        majitel = Zamestnanec.objects.get(salon=salon, role=Zamestnanec.ROLE_MAJITEL)
        self.assertEqual(majitel.jmeno, 'Manager')
        self.assertFalse(majitel.zobrazit_na_webu)
        self.assertEqual(majitel.prihlasovaci_jmeno, 'majitel@autoservis-test.cz')
        self.assertTrue(majitel.check_password('DocasneHeslo99'))
        self.assertTrue(hasattr(majitel, 'flow_ucet'))
        self.assertEqual(majitel.flow_ucet.email, 'majitel@autoservis-test.cz')
        self.assertFalse(
            Zamestnanec.objects.filter(salon=salon, role=Zamestnanec.ROLE_ZAMESTNANEC).exists()
        )
        self.assertTrue(
            SalonAuditLog.objects.filter(salon=salon, popis__icontains='Založen nový partner').exists()
        )

    def test_zpetne_nahrani_a_smazani_faktury_pdf(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.client.force_login(self.superuser)
        platba = PlatbaPartnera.objects.create(
            salon=self.salon,
            splatnost=date(2026, 7, 15),
            zaplaceno_dne=date(2026, 8, 7),
            ocekavana_castka=Decimal('499.00'),
            prijata_castka=Decimal('499.00'),
            variabilni_symbol='500',
            oznacil=self.superuser,
        )
        pdf = SimpleUploadedFile('faktura.pdf', b'%PDF-1.4 test', content_type='application/pdf')
        response = self.client.post(
            reverse('partner_admin:nahrat_fakturu', args=[self.salon.id, platba.id]),
            {'faktura_pdf': pdf},
        )
        self.assertEqual(response.status_code, 302)
        platba.refresh_from_db()
        self.assertTrue(platba.faktura_pdf)
        self.assertTrue(platba.faktura_pdf.name.endswith('.pdf'))

        response = self.client.post(
            reverse('partner_admin:smazat_fakturu', args=[self.salon.id, platba.id]),
        )
        self.assertEqual(response.status_code, 302)
        platba.refresh_from_db()
        self.assertFalse(platba.faktura_pdf)

    def test_detail_ukazuje_materialnik_vypnuto(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse('partner_admin:detail', args=[self.salon.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Materiálník')
        self.assertContains(response, 'Zapnout Materiálník')

    def test_zapnout_materialnik_stub(self):
        self.client.force_login(self.superuser)
        with self.settings(MATERIALNIK_STUB=True, MATERIALNIK_PUBLIC_URL='http://127.0.0.1:8001'):
            response = self.client.post(
                reverse('partner_admin:nastavit_materialnik', args=[self.salon.id]),
                {'zapnout': '1'},
            )
        self.assertEqual(response.status_code, 302)
        from partner_admin.models import PartnerModul
        row = PartnerModul.objects.get(salon=self.salon, modul__kod='materialnik')
        self.assertEqual(row.status, PartnerModul.STAV_ACTIVE)
        self.assertTrue(row.hmac_key)

        with self.settings(MATERIALNIK_STUB=True):
            response = self.client.post(
                reverse('partner_admin:nastavit_materialnik', args=[self.salon.id]),
                {'zapnout': '0'},
            )
        self.assertEqual(response.status_code, 302)
        row.refresh_from_db()
        self.assertEqual(row.status, PartnerModul.STAV_INACTIVE)

    def test_katalog_tarifu_a_vyber_u_partnera(self):
        self.client.force_login(self.superuser)
        modernik = PartnerTarif.objects.get(nazev='Moderník')
        modernik.castka = Decimal('1490.00')
        modernik.save()

        katalog = self.client.get(reverse('partner_admin:tarify'))
        self.assertEqual(katalog.status_code, 200)
        self.assertContains(katalog, 'Moderník')
        self.assertContains(katalog, 'Materiálník')
        self.assertContains(katalog, 'Partnerský web')

        response = self.client.post(
            reverse('partner_admin:tarify'),
            {
                'akce': 'ulozit',
                'id': str(modernik.id),
                'nazev': 'Moderník',
                'castka': '1 590,00',
                'razeni': '1',
                'aktivni': 'on',
            },
        )
        self.assertEqual(response.status_code, 302)
        modernik.refresh_from_db()
        self.assertEqual(modernik.castka, Decimal('1590.00'))

        detail = self.client.get(reverse('partner_admin:detail', args=[self.salon.id]))
        html = detail.content.decode()
        self.assertIn('name="tarif"', html)
        self.assertIn('data-cena="1590,00"', html)
        self.assertIn('>Moderník<', html)
        self.assertIn('haklweb.b-cdn.net', detail.headers.get('Content-Security-Policy', ''))

        response = self.client.post(
            reverse('partner_admin:ulozit_nastaveni', args=[self.salon.id]),
            {
                'domena': 'kudrlinka-test.cz',
                'tarif': 'Moderník',
                'fakturacni_email': 'fakturace@kudrlinka-test.cz',
                'variabilni_symbol': '1900000019',
                'periodicita': PartnerNastaveni.PERIODA_MESIC,
                'castka': '1400,00',
                'dalsi_splatnost': '2026-09-01',
                'tab': 'partner',
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.partner.refresh_from_db()
        self.assertEqual(self.partner.tarif, 'Moderník')
        self.assertEqual(self.partner.castka, Decimal('1400.00'))
        html = response.content.decode()
        self.assertIn('tarif: Moderník', html)
        self.assertIn('<dt>Tarif</dt>', html)
        self.assertIn('modernik/modernik_logo.webp', html)
        self.assertIn('value="1400,00"', html)

    def test_pridani_tarifu_do_katalogu(self):
        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse('partner_admin:tarify'),
            {
                'akce': 'pridat',
                'nazev': 'Zkušební tarif',
                'castka': '99,00',
                'razeni': '9',
                'aktivni': 'on',
            },
        )
        self.assertEqual(response.status_code, 302)
        tarif = PartnerTarif.objects.get(nazev='Zkušební tarif')
        self.assertEqual(tarif.castka, Decimal('99.00'))
        detail = self.client.get(reverse('partner_admin:detail', args=[self.salon.id]))
        self.assertContains(detail, 'Zkušební tarif')
        self.assertContains(detail, 'data-cena="99,00"')
        self.assertContains(detail, 'New%20Project.webp')

    def test_logo_tarifu_podle_nazvu(self):
        from partner_admin.loga import (
            LOGO_MATERIALNIK,
            LOGO_MODERNIK,
            LOGO_OSTATNI,
            LOGO_SPOJENI,
            LOGO_WEB,
            logo_url_pro_tarif,
        )
        self.assertEqual(logo_url_pro_tarif('Moderník'), LOGO_MODERNIK)
        self.assertEqual(logo_url_pro_tarif('Materiálník'), LOGO_MATERIALNIK)
        self.assertEqual(logo_url_pro_tarif('Moderník + Materiálník'), LOGO_SPOJENI)
        self.assertEqual(logo_url_pro_tarif('WEB'), LOGO_WEB)
        self.assertEqual(logo_url_pro_tarif('Partnerský web'), LOGO_OSTATNI)
        self.assertEqual(logo_url_pro_tarif(''), LOGO_OSTATNI)

    def test_hromadny_email_jde_vsem_s_adresou(self):
        self.client.force_login(self.superuser)
        self.assertEqual(self.client.get(reverse('partner_admin:emaily')).status_code, 200)
        response = self.client.post(
            reverse('partner_admin:emaily'),
            {
                'okruh': 'vsichni',
                'predmet': 'Info pro partnery',
                'text': 'Nový ceník od září.',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['platby@example.test'])
        self.assertTrue(
            HromadnyEmail.objects.filter(predmet='Info pro partnery', odeslano_pocet=1).exists()
        )

    def test_technicka_chyba_uchova_zpravu_a_query_bez_tajemstvi(self):
        from django.test import RequestFactory

        from partner_admin.middleware import TechnickeChybyMiddleware

        request = RequestFactory().get(
            f'/api/salon/{self.salon.id}/',
            {'token': 'tajne', 'q': 'rezervace'},
        )
        TechnickeChybyMiddleware(lambda req: None).process_exception(
            request,
            ValueError('SMTP salonu neodpovídá'),
        )
        chyba = TechnickaChyba.objects.get()
        self.assertEqual(chyba.typ_chyby, 'ValueError')
        self.assertIn('SMTP', chyba.detail)
        self.assertIn('token=***', chyba.query)
        self.assertIn('q=rezervace', chyba.query)
        self.assertNotIn('tajne', chyba.query)
        self.assertIn('ValueError', chyba.stopa)

        self.client.force_login(self.superuser)
        detail = self.client.get(reverse('partner_admin:chyba_detail', args=[chyba.id]))
        self.assertContains(detail, 'SMTP salonu neodpovídá')
        self.assertContains(detail, 'ValueError')

    def test_detail_partnera_ma_svisle_menu(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse('partner_admin:detail', args=[self.salon.id]))
        self.assertContains(response, 'detail-side')
        self.assertNotContains(response, 'detail-tabs')
