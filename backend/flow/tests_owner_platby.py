"""I6 — FLOW majitel: read-only platby partnera + overdue."""

from datetime import date, timedelta
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase

from flow.auth import flow_user_do_dict
from flow.models import FlowUser
from partner_admin.models import PlatbaPartnera
from partner_admin.services import oznac_platbu
from rezervace.models import Zamestnanec
from salons.models import Salon


class FlowOwnerPlatbyTests(TestCase):
    def setUp(self):
        self.salon = Salon.objects.create(name='Salon I6')
        self.owner = Zamestnanec.objects.create(
            salon=self.salon,
            jmeno='Owner',
            role=Zamestnanec.ROLE_MAJITEL,
            prihlasovaci_jmeno='owner-i6@test.local',
            aktivni=True,
            zobrazit_na_webu=False,
        )
        self.owner.set_password('Heslo1234')
        self.owner.save(update_fields=['password_hash'])
        self.flow_owner = FlowUser.objects.create(
            salon=self.salon,
            zamestnanec=self.owner,
            email='owner-i6@test.local',
            aktivni=True,
            visible_overview=True,
        )
        self.flow_owner.password_hash = self.owner.password_hash
        self.flow_owner.save(update_fields=['password_hash'])

        self.staff = Zamestnanec.objects.create(
            salon=self.salon,
            jmeno='Staff',
            role=Zamestnanec.ROLE_ZAMESTNANEC,
            prihlasovaci_jmeno='staff-i6@test.local',
            aktivni=True,
            zobrazit_na_webu=True,
        )
        self.staff.set_password('Staff1234')
        self.staff.save(update_fields=['password_hash'])
        self.flow_staff = FlowUser.objects.create(
            salon=self.salon,
            zamestnanec=self.staff,
            email='staff-i6@test.local',
            aktivni=True,
        )
        self.flow_staff.set_password('Staff1234')
        self.flow_staff.save(update_fields=['password_hash'])
        self.client = Client()

    def _login(self, email, password):
        r = self.client.post(
            '/api/flow/prihlaseni/',
            data={'email': email, 'password': password},
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()['token']

    def test_empty_without_partner_settings(self):
        from partner_admin.models import PartnerNastaveni

        PartnerNastaveni.objects.filter(salon=self.salon).delete()
        token = self._login('owner-i6@test.local', 'Heslo1234')
        r = self.client.get('/api/flow/owner/platby/', HTTP_X_FLOW_TOKEN=token)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertFalse(data['nastaveno'])
        self.assertFalse(data['je_po_splatnosti'])
        self.assertEqual(data['historie'], [])

    def test_staff_forbidden(self):
        token = self._login('staff-i6@test.local', 'Staff1234')
        r = self.client.get('/api/flow/owner/platby/', HTTP_X_FLOW_TOKEN=token)
        self.assertEqual(r.status_code, 403)

    def test_overdue_payload_and_me_badge(self):
        nast = self.salon.partner_nastaveni
        nast.variabilni_symbol = '123456'
        nast.castka = Decimal('1990.00')
        nast.dalsi_splatnost = date.today() - timedelta(days=5)
        nast.ulov_cislo_uctu = '123456789/0100'
        nast.save()
        token = self._login('owner-i6@test.local', 'Heslo1234')
        r = self.client.get('/api/flow/owner/platby/', HTTP_X_FLOW_TOKEN=token)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data['nastaveno'])
        self.assertTrue(data['je_po_splatnosti'])
        self.assertEqual(data['dni_po_splatnosti'], 5)
        self.assertEqual(data['variabilni_symbol'], '123456')
        self.assertEqual(data['ulov_cislo_uctu'], '123456789/0100')
        self.assertIsNotNone(data['qr'])
        self.assertIn('qr_png_base64', data['qr'])

        me = self.client.get('/api/flow/me/', HTTP_X_FLOW_TOKEN=token)
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()['po_splatnosti_dni'], 5)

        d = flow_user_do_dict(self.flow_owner)
        self.assertEqual(d['po_splatnosti_dni'], 5)

    def test_historie_and_faktura_download(self):
        from django.contrib.auth import get_user_model

        nast = self.salon.partner_nastaveni
        nast.variabilni_symbol = '654321'
        nast.castka = Decimal('990.00')
        nast.dalsi_splatnost = date.today() + timedelta(days=20)
        nast.ulov_cislo_uctu = '123456789/0100'
        nast.save()
        admin = get_user_model().objects.create_user(username='pa-i6', password='x')
        pdf = SimpleUploadedFile('faktura.pdf', b'%PDF-1.4 fake', content_type='application/pdf')
        platba = oznac_platbu(
            self.salon,
            user=admin,
            zaplaceno_dne=date.today(),
            prijata_castka=Decimal('990.00'),
            faktura_pdf=pdf,
        )
        self.assertTrue(isinstance(platba, PlatbaPartnera))
        self.assertTrue(platba.faktura_pdf)

        token = self._login('owner-i6@test.local', 'Heslo1234')
        r = self.client.get('/api/flow/owner/platby/', HTTP_X_FLOW_TOKEN=token)
        self.assertEqual(r.status_code, 200)
        hist = r.json()['historie']
        self.assertEqual(len(hist), 1)
        self.assertTrue(hist[0]['ma_fakturu'])

        dl = self.client.get(
            f'/api/flow/owner/platby/{platba.id}/faktura/',
            HTTP_X_FLOW_TOKEN=token,
        )
        self.assertEqual(dl.status_code, 200)
        self.assertEqual(dl['Content-Type'], 'application/pdf')
        body = b''.join(dl.streaming_content)
        self.assertTrue(body.startswith(b'%PDF'))

    def test_extra_faktura_je_v_platbach_a_jde_stahnout(self):
        from datetime import timedelta

        from django.utils import timezone

        from partner_admin.faktura import dalsi_cislo_faktury, uloz_fakturu_extra, vs_extra_z_cisla
        from partner_admin.models import ExtraFaktura

        nast = self.salon.partner_nastaveni
        nast.ulov_cislo_uctu = '123456789/0100'
        nast.variabilni_symbol = '8019'
        nast.castka = Decimal('990.00')
        nast.save()
        cislo = dalsi_cislo_faktury()
        extra = ExtraFaktura.objects.create(
            salon=self.salon,
            cislo_faktury=cislo,
            variabilni_symbol=vs_extra_z_cisla(cislo),
            popis='NFC stojánek',
            castka=Decimal('1200.00'),
            stav=ExtraFaktura.STAV_K_UHRADE,
            datum_vystaveni=timezone.localdate(),
            datum_splatnosti=timezone.localdate() + timedelta(days=14),
        )
        uloz_fakturu_extra(extra)
        token = self._login('owner-i6@test.local', 'Heslo1234')
        r = self.client.get('/api/flow/owner/platby/', HTTP_X_FLOW_TOKEN=token)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(len(data['extra_k_uhrade']), 1)
        self.assertEqual(data['extra_k_uhrade'][0]['popis'], 'NFC stojánek')
        self.assertTrue(any(row['typ'] == 'extra' for row in data['historie']))
        dl = self.client.get(
            f'/api/flow/owner/extra-faktury/{extra.id}/faktura/',
            HTTP_X_FLOW_TOKEN=token,
        )
        self.assertEqual(dl.status_code, 200)
        self.assertTrue(b''.join(dl.streaming_content).startswith(b'%PDF'))
