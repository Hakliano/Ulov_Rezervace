from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from salons.models import Salon

from .faktura import dalsi_cislo_faktury, vs_extra_z_cisla
from .models import ExtraFaktura, PlatbaPartnera, UlovCisloUctu, Vydaj, VydajSablona


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class EvidenceFakturAVydajuTests(TestCase):
    def setUp(self):
        self.salon = Salon.objects.create(name='Salon Extra', email='extra@example.test')
        self.partner = self.salon.partner_nastaveni
        self.partner.fakturacni_email = 'fakturace@example.test'
        self.partner.variabilni_symbol = '8019'
        self.partner.castka = Decimal('499.00')
        self.partner.dalsi_splatnost = date(2026, 9, 30)
        self.partner.save()
        self.superuser = get_user_model().objects.create_superuser(
            username='sa-evidence',
            email='sa-ev@example.test',
            password='bezpecne-test-heslo',
        )
        self.ucet = UlovCisloUctu.objects.create(
            cislo='123456789/0100',
            popisek='Fio',
            primarni=True,
            aktivni=True,
        )
        self.client.force_login(self.superuser)

    def test_vs_extra_z_cisla(self):
        self.assertEqual(vs_extra_z_cisla('2026-0042'), '620260042')

    def test_cisla_faktur_sdili_radu(self):
        PlatbaPartnera.objects.create(
            salon=self.salon,
            splatnost=date(2026, 1, 31),
            zaplaceno_dne=date(2026, 1, 20),
            ocekavana_castka=Decimal('499.00'),
            prijata_castka=Decimal('499.00'),
            cislo_faktury='2026-0003',
        )
        ExtraFaktura.objects.create(
            salon=self.salon,
            cislo_faktury='2026-0007',
            popis='NFC',
            castka=Decimal('800.00'),
            stav=ExtraFaktura.STAV_UHRAZENO,
            datum_vystaveni=date(2026, 2, 1),
            datum_uhrady=date(2026, 2, 1),
        )
        self.assertEqual(dalsi_cislo_faktury(2026), '2026-0008')

    def test_extra_faktura_k_uhrade_ma_splatnost_a_nemeni_tarif(self):
        pred = self.partner.dalsi_splatnost
        resp = self.client.post(
            reverse('partner_admin:vytvorit_extra_fakturu', args=[self.salon.id]),
            {
                'popis': 'NFC stojánek, 4 ks',
                'castka': '1200,00',
                'stav': ExtraFaktura.STAV_K_UHRADE,
                'odeslat_email': 'on',
            },
        )
        self.assertEqual(resp.status_code, 302)
        faktura = ExtraFaktura.objects.get(salon=self.salon)
        self.assertEqual(faktura.stav, ExtraFaktura.STAV_K_UHRADE)
        self.assertEqual(faktura.datum_splatnosti, timezone.localdate() + timedelta(days=14))
        self.assertTrue(faktura.variabilni_symbol.startswith('6'))
        self.assertTrue(faktura.faktura_pdf)
        self.partner.refresh_from_db()
        self.assertEqual(self.partner.dalsi_splatnost, pred)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(faktura.cislo_faktury, mail.outbox[0].subject)

        seznam = self.client.get(reverse('partner_admin:faktury'))
        self.assertEqual(seznam.status_code, 200)
        self.assertContains(seznam, faktura.cislo_faktury)
        self.assertContains(seznam, 'NFC stojánek')

    def test_extra_uhrada_nemeni_splatnost(self):
        self.client.post(
            reverse('partner_admin:vytvorit_extra_fakturu', args=[self.salon.id]),
            {
                'popis': 'Vizitky',
                'castka': '350',
                'stav': ExtraFaktura.STAV_K_UHRADE,
            },
        )
        faktura = ExtraFaktura.objects.get()
        pred = self.partner.dalsi_splatnost
        resp = self.client.post(
            reverse('partner_admin:extra_faktura_uhrazena', args=[self.salon.id, faktura.id]),
        )
        self.assertEqual(resp.status_code, 302)
        faktura.refresh_from_db()
        self.assertEqual(faktura.stav, ExtraFaktura.STAV_UHRAZENO)
        self.partner.refresh_from_db()
        self.assertEqual(self.partner.dalsi_splatnost, pred)

    def test_vydaj_a_sablona(self):
        resp = self.client.post(
            reverse('partner_admin:vydaje'),
            {
                'datum': timezone.localdate().isoformat(),
                'castka': '890,00',
                'ucet': str(self.ucet.id),
                'poznamka': 'Hetzner',
                'ulozit_sablonu': 'on',
                'nazev_sablony': 'Hetzner',
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Vydaj.objects.count(), 1)
        self.assertTrue(VydajSablona.objects.filter(nazev='Hetzner').exists())
        dash = self.client.get(reverse('partner_admin:dashboard'))
        self.assertContains(dash, 'Výdaje tento měsíc')
        self.assertContains(dash, '890')
        from .prehled import data_prehledu
        prehled = data_prehledu(timezone.localdate())
        self.assertEqual(prehled['vydaje_mesic'], Decimal('890.00'))
        self.assertEqual(prehled['zisk_mesic'], Decimal('-890.00'))

    def test_souhrn_pdf(self):
        self.client.post(
            reverse('partner_admin:vytvorit_extra_fakturu', args=[self.salon.id]),
            {
                'popis': 'NFC stojánek',
                'castka': '1200',
                'stav': ExtraFaktura.STAV_UHRAZENO,
            },
        )
        resp = self.client.get(reverse('partner_admin:faktury') + '?souhrn=pdf')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertTrue(resp.content.startswith(b'%PDF'))
        self.assertGreater(len(resp.content), 2000)
