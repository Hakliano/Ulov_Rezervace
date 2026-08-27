from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from rezervace.models import SalonAuditLog, Zamestnanec, ZamestnanecSession
from salons.models import Salon

from .models import (
    HromadnyEmail,
    KamProvize,
    KeyAccountManager,
    PartnerNastaveni,
    PartnerTarif,
    PlatbaPartnera,
    TechnickaChyba,
    UlovCisloUctu,
    UpozorneniPlatby,
)
from .services import oznac_platbu, posun_splatnost


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
        platba = PlatbaPartnera.objects.get(salon=self.salon, splatnost=date(2026, 1, 31))
        self.assertTrue(platba.faktura_pdf)
        self.assertTrue(platba.cislo_faktury)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(platba.cislo_faktury, mail.outbox[0].subject)
        parovani = self.client.get(reverse('partner_admin:detail', args=[self.salon.id]) + '?tab=parovani')
        self.assertContains(parovani, 'Otevřít PDF')
        self.assertContains(parovani, platba.cislo_faktury)

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
        self.assertEqual(self.partner.ulov_cislo_uctu, '')
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
        self.assertFalse(partner.je_testovaci)

    def test_novy_salon_dostane_vs_80_id(self):
        salon = Salon.objects.create(name='Auto VS salon', email='autovs@example.test')
        self.assertEqual(salon.partner_nastaveni.variabilni_symbol, f'80{salon.id}')

    def test_hledani_partnera_podle_vs_a_id(self):
        vs = f'80{self.salon.id}'
        self.partner.variabilni_symbol = vs
        self.partner.save()
        self.client.force_login(self.superuser)
        podle_vs = self.client.get(reverse('partner_admin:partneri'), {'q': vs})
        self.assertContains(podle_vs, 'Test Salon')
        self.assertContains(podle_vs, vs)
        podle_id = self.client.get(reverse('partner_admin:partneri'), {'q': str(self.salon.id)})
        self.assertContains(podle_id, 'Test Salon')
        nic = self.client.get(reverse('partner_admin:partneri'), {'q': '999000111'})
        self.assertNotContains(nic, 'Test Salon')

    def test_novy_partner_bez_vs_dostane_80_id(self):
        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse('partner_admin:novy'),
            {
                'name': 'Partner Bez VS',
                'majitel_email': 'majitel-vs@example.test',
                'majitel_heslo': 'DocasneHeslo99',
                'aktivovat_flow': 'on',
                'periodicita': PartnerNastaveni.PERIODA_MESIC,
                'castka': '499.00',
            },
        )
        self.assertEqual(response.status_code, 302)
        salon = Salon.objects.get(name='Partner Bez VS')
        self.assertEqual(salon.partner_nastaveni.variabilni_symbol, f'80{salon.id}')

    def test_prazdny_vs_pri_ulozeni_vrati_80_id(self):
        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse('partner_admin:ulozit_nastaveni', args=[self.salon.id]),
            {
                'domena': '',
                'tarif': 'Partner pro váš salon',
                'fakturacni_email': 'platby@example.test',
                'variabilni_symbol': '',
                'periodicita': PartnerNastaveni.PERIODA_MESIC,
                'castka': '499.00',
                'dalsi_splatnost': '2026-01-31',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.partner.refresh_from_db()
        self.assertEqual(self.partner.variabilni_symbol, f'80{self.salon.id}')

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

    def test_testovaci_pristupy_jen_oznacene_salony(self):
        self.partner.je_testovaci = True
        self.partner.save()
        zakaznik = Salon.objects.create(name='Ostrý zákazník')
        zakaznik.partner_nastaveni.je_testovaci = False
        zakaznik.partner_nastaveni.save()
        self.client.force_login(self.superuser)
        response = self.client.get(reverse('partner_admin:testovaci_pristupy'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Salon')
        self.assertContains(response, 'majitelka')
        self.assertContains(response, 'Vygenerovat heslo')
        self.assertNotContains(response, 'Ostrý zákazník')
        self.assertNotContains(response, 'puvodni-heslo')

    def test_regenerace_demo_hesla_ukaze_jednou(self):
        self.partner.je_testovaci = True
        self.partner.save()
        self.majitel.prihlasovaci_jmeno = 'demo@ulov.local'
        self.majitel.save(update_fields=['prihlasovaci_jmeno'])
        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse('partner_admin:regenerovat_demo_heslo', args=[self.salon.id]),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.majitel.refresh_from_db()
        self.assertFalse(self.majitel.check_password('puvodni-heslo'))
        html = response.content.decode()
        self.assertIn('Nové heslo', html)
        znovu = self.client.get(reverse('partner_admin:testovaci_pristupy'))
        self.assertNotIn('Nové heslo — zkopíruj teď', znovu.content.decode())

    def test_partneri_sloupec_materialnik_a_kam(self):
        from partner_admin.models import MODUL_MATERIALNIK, ModulKatalog, PartnerModul

        kam = KeyAccountManager.objects.create(jmeno='Viktor Test')
        self.partner.kam = kam
        self.partner.save()
        katalog, _ = ModulKatalog.objects.get_or_create(
            kod=MODUL_MATERIALNIK,
            defaults={'nazev': 'Materiálník', 'razeni': 10},
        )
        PartnerModul.objects.create(
            salon=self.salon,
            modul=katalog,
            status=PartnerModul.STAV_ACTIVE,
        )
        self.client.force_login(self.superuser)
        response = self.client.get(reverse('partner_admin:partneri'))
        self.assertContains(response, 'Materiálník')
        self.assertContains(response, 'Aktivní')
        self.assertContains(response, 'KAM Viktor Test')

    def test_globalni_ucet_se_prepise_na_vsechny_salony(self):
        jiny = Salon.objects.create(name='Druhý salon')
        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse('partner_admin:ucty'),
            {
                'akce': 'pridat',
                'cislo': '111222333/0100',
                'popisek': 'Fio',
                'primarni': 'on',
                'razeni': '10',
                'aktivni': 'on',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.partner.refresh_from_db()
        jiny.partner_nastaveni.refresh_from_db()
        self.assertEqual(self.partner.ulov_cislo_uctu, '111222333/0100')
        self.assertEqual(jiny.partner_nastaveni.ulov_cislo_uctu, '111222333/0100')
        seznam = self.client.get(reverse('partner_admin:ucty'))
        self.assertContains(seznam, '111222333/0100')

    def test_kam_stranka_ukaze_prirazene_provozovny(self):
        kam = KeyAccountManager.objects.create(
            jmeno='Anna Obchod',
            email='anna@example.test',
            telefon='777111222',
            cislo_uctu='111222333/0100',
        )
        self.partner.kam = kam
        self.partner.tarif = 'Moderník'
        self.partner.save()
        from django.utils import timezone
        dnes = timezone.localdate()
        KamProvize.objects.create(
            kam=kam,
            salon=self.salon,
            typ=KamProvize.TYP_PRVNI,
            obdobi=dnes.replace(day=1),
            castka=Decimal('1500.00'),
            uvolneno_dne=dnes,
        )
        stary = Salon.objects.create(name='Starý salon', email='stary@example.test')
        stare_obdobi = date(dnes.year - 1, 12, 1) if dnes.month == 1 else date(dnes.year, dnes.month - 1, 1)
        KamProvize.objects.create(
            kam=kam,
            salon=stary,
            typ=KamProvize.TYP_PRVNI,
            obdobi=stare_obdobi,
            castka=Decimal('500.00'),
            uvolneno_dne=stare_obdobi,
        )
        self.client.force_login(self.superuser)
        response = self.client.get(reverse('partner_admin:kam'))
        self.assertContains(response, 'Anna Obchod')
        self.assertContains(response, 'Test Salon')
        self.assertContains(response, 'Číslo účtu')
        self.assertContains(response, 'Výpis provizí')
        self.assertContains(response, 'Upravit')
        self.assertContains(response, 'Vydělal tento měsíc')
        self.assertContains(response, 'Celkem')
        self.assertNotContains(response, 'name="akce" value="ulozit"')
        karta = next(radek for radek in response.context['karty'] if radek['kam'].pk == kam.pk)
        self.assertEqual(karta['mesic'], Decimal('1500.00'))
        self.assertEqual(karta['celkem'], Decimal('2000.00'))
        self.assertFalse(karta['edituje'])

        editace = self.client.get(reverse('partner_admin:kam'), {'upravit': kam.id})
        self.assertContains(editace, 'name="akce" value="ulozit"')
        self.assertContains(editace, 'Uložit')
        self.assertContains(editace, 'Zrušit')
        edit_karta = next(radek for radek in editace.context['karty'] if radek['kam'].pk == kam.pk)
        self.assertTrue(edit_karta['edituje'])


class KamProvizeAFakturaTests(TestCase):
    def setUp(self):
        from django.utils import timezone

        self.dnes = timezone.localdate()
        self.salon = Salon.objects.create(name='Salon Kryštof', email='krystof@example.test')
        self.partner = self.salon.partner_nastaveni
        self.partner.castka = Decimal('499.00')
        self.partner.dalsi_splatnost = self.dnes
        self.partner.variabilni_symbol = '24552488'
        self.partner.ico = '12345678'
        self.kam = KeyAccountManager.objects.create(
            jmeno='Kryštof',
            cislo_uctu='123456789/0100',
        )
        self.partner.kam = self.kam
        self.partner.save()
        self.superuser = get_user_model().objects.create_superuser(
            username='superadmin-kam',
            email='admin-kam@example.test',
            password='bezpecne-test-heslo',
        )

    def _nastav(self, prvni, provize, procento=0):
        self.partner.prvni_platba = Decimal(str(prvni))
        self.partner.kam_provize = Decimal(str(provize))
        self.partner.kam_procento = Decimal(str(procento))
        self.partner.dalsi_splatnost = self.dnes
        self.partner.save()

    def test_krystof_2000_1500_ulov_necha_500(self):
        self._nastav(2000, 1500)
        platba = oznac_platbu(self.salon, self.superuser, self.dnes, Decimal('2000.00'))
        self.assertEqual(platba.ocekavana_castka, Decimal('2000.00'))
        row = KamProvize.objects.get(salon=self.salon)
        self.assertEqual(row.castka, Decimal('1500.00'))
        self.assertEqual(row.typ, KamProvize.TYP_PRVNI)
        self.assertEqual(row.stav, KamProvize.STAV_K_VYPLATE)
        from .prehled import data_prehledu
        prehled = data_prehledu(self.dnes)
        self.assertEqual(prehled['prijato_mesic'], Decimal('2000.00'))
        self.assertEqual(prehled['kam_mesic'], Decimal('1500.00'))
        self.assertEqual(prehled['zisk_mesic'], Decimal('500.00'))

    def test_krystof_499_1200_jde_z_kapsy_ulov(self):
        self._nastav(499, 1200)
        oznac_platbu(self.salon, self.superuser, self.dnes, Decimal('499.00'))
        self.assertEqual(KamProvize.objects.get(salon=self.salon).castka, Decimal('1200.00'))
        from .prehled import data_prehledu
        self.assertEqual(data_prehledu(self.dnes)['zisk_mesic'], Decimal('-701.00'))

    def test_krystof_1000_1500_jde_z_kapsy_ulov(self):
        self._nastav(1000, 1500)
        oznac_platbu(self.salon, self.superuser, self.dnes, Decimal('1000.00'))
        from .prehled import data_prehledu
        self.assertEqual(data_prehledu(self.dnes)['zisk_mesic'], Decimal('-500.00'))

    def test_provize_nula_nevytvori_radek(self):
        self._nastav(2000, 0)
        oznac_platbu(self.salon, self.superuser, self.dnes, Decimal('2000.00'))
        self.assertFalse(KamProvize.objects.filter(salon=self.salon).exists())

    def test_druha_platba_neprida_dalsi_provizi(self):
        self._nastav(2000, 1500)
        oznac_platbu(self.salon, self.superuser, self.dnes, Decimal('2000.00'))
        self.partner.refresh_from_db()
        oznac_platbu(self.salon, self.superuser, self.dnes, Decimal('499.00'))
        self.assertEqual(KamProvize.objects.filter(salon=self.salon).count(), 1)

    def test_vypis_a_vyplaceni_mesice(self):
        self._nastav(2000, 1500)
        oznac_platbu(self.salon, self.superuser, self.dnes, Decimal('2000.00'))
        self.client.force_login(self.superuser)
        url = reverse('partner_admin:kam_vypis', args=[self.kam.id])
        response = self.client.get(url, {'rok': self.dnes.year, 'mesic': self.dnes.month})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Kryštof')
        self.assertContains(response, '123456789/0100')
        self.assertEqual(response.context['k_vyplate'], Decimal('1500.00'))
        self.client.post(
            reverse('partner_admin:kam_vyplatit', args=[self.kam.id]),
            {'rok': self.dnes.year, 'mesic': self.dnes.month},
        )
        row = KamProvize.objects.get(salon=self.salon)
        self.assertEqual(row.stav, KamProvize.STAV_VYPLACENO)

    def test_faktura_sablona_a_generovani_s_cestinou(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from partner_admin import faktura as faktura_mod
        from reportlab.pdfbase.pdfmetrics import stringWidth

        self.salon.address = 'Praha - Záběhlice'
        self.salon.save()
        platba = PlatbaPartnera.objects.create(
            salon=self.salon,
            splatnost=self.dnes,
            zaplaceno_dne=self.dnes,
            ocekavana_castka=Decimal('499.00'),
            prijata_castka=Decimal('499.00'),
            variabilni_symbol='24552488',
            oznacil=self.superuser,
        )
        self.client.force_login(self.superuser)
        pripravit = reverse('partner_admin:pripravit_fakturu', args=[self.salon.id, platba.id])
        get_resp = self.client.get(pripravit)
        self.assertEqual(get_resp.status_code, 200)
        self.assertContains(get_resp, 'Jiří Hakl')
        self.assertContains(get_resp, '24552488')
        self.assertContains(get_resp, 'Záběhlice')
        self.assertContains(get_resp, 'živnostenském rejstříku')
        self.assertContains(get_resp, 'Vygenerovat PDF')

        faktura_mod._FONTY_NACTENY = False
        data = faktura_mod.vychozi_data_faktury(platba)
        post = self.client.post(pripravit, data)
        self.assertEqual(post.status_code, 302)
        platba.refresh_from_db()
        self.assertTrue(platba.faktura_pdf)
        self.assertTrue(platba.cislo_faktury)
        obsah = platba.faktura_pdf.read()
        platba.faktura_pdf.close()
        self.assertTrue(obsah.startswith(b'%PDF'))
        regular, _ = faktura_mod.nacti_fonty()
        if regular == 'Helvetica':
            self.fail('Chybí Unicode TTF (Arial / DejaVu). PDF by zničilo češtinu.')
        self.assertEqual(regular, 'UlovSans')
        self.assertGreater(stringWidth('Jiří Záběhlice řěšč', regular, 12), 0)
        self.assertTrue(
            b'/Subtype /TrueType' in obsah or b'FontFile2' in obsah,
            'PDF nemá vložený Unicode TrueType font.',
        )

        pdf = SimpleUploadedFile('rucni.pdf', b'%PDF-1.4 rucni', content_type='application/pdf')
        nahrat = self.client.post(
            reverse('partner_admin:nahrat_fakturu', args=[self.salon.id, platba.id]),
            {'faktura_pdf': pdf},
        )
        self.assertEqual(nahrat.status_code, 302)
        platba.refresh_from_db()
        self.assertTrue(platba.faktura_pdf.name.endswith('.pdf'))

    def test_faktura_obdobi_splatnost_a_evidence(self):
        from datetime import date

        from partner_admin.faktura import vychozi_data_faktury

        self.partner.tarif = 'Moderník'
        self.partner.periodicita = PartnerNastaveni.PERIODA_MESIC
        self.partner.save()
        platba = PlatbaPartnera.objects.create(
            salon=self.salon,
            splatnost=date(2026, 9, 26),
            zaplaceno_dne=date(2026, 8, 27),
            ocekavana_castka=Decimal('499.00'),
            prijata_castka=Decimal('499.00'),
            variabilni_symbol='24552488',
            oznacil=self.superuser,
        )
        data = vychozi_data_faktury(platba)
        self.assertEqual(data['datum_uhrady'], '2026-08-27')
        self.assertEqual(data['polozka'], 'Moderník – Partnerství')
        self.assertEqual(data['obdobi'], '27. 8. 2026 – 26. 9. 2026')
        self.assertEqual(data['stav'], 'UHRAZENO')
        self.assertEqual(data['zpusob_uhrady'], 'převodem')
        self.assertEqual(
            data['dodavatel_evidence'],
            'Fyzická osoba zapsaná v živnostenském rejstříku',
        )
        self.assertEqual(data['dodavatel_znacka'], 'ULOV KLIENTY')

    def test_faktura_k_platbe_vznikne_jen_jednou(self):
        from partner_admin.faktura import zajisti_fakturu

        platba = oznac_platbu(self.salon, self.superuser, self.dnes, Decimal('499.00'))
        self.assertTrue(platba.faktura_pdf)
        cislo = platba.cislo_faktury
        znovu, nova = zajisti_fakturu(platba)
        self.assertFalse(nova)
        self.assertEqual(znovu.cislo_faktury, cislo)
        self.client.force_login(self.superuser)
        response = self.client.post(
            reverse('partner_admin:vygenerovat_fakturu', args=[self.salon.id, platba.id]),
            {'tab': 'parovani'},
        )
        self.assertEqual(response.status_code, 302)
        platba.refresh_from_db()
        self.assertEqual(platba.cislo_faktury, cislo)

