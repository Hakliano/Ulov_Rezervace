from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from rezervace.models import SalonAuditLog, Zamestnanec, ZamestnanecSession
from salons.models import Salon

from .models import PartnerNastaveni, PlatbaPartnera, UpozorneniPlatby
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
        response = self.client.get(reverse('partner_admin:dashboard'), {'platba': 'po_splatnosti'})
        self.assertContains(response, 'Test Salon')
        self.assertContains(response, f'+{self.partner.dni_po_splatnosti} dní')

        response = self.client.get(reverse('partner_admin:dashboard'), {'platba': 'bez_vs'})
        self.assertContains(response, 'Bez VS')
        self.assertNotContains(response, 'Test Salon')

        response = self.client.get(reverse('partner_admin:dashboard'), {'stav': 'active'})
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
        response = self.client.get(reverse('partner_admin:detail', args=[self.salon.id]))
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
