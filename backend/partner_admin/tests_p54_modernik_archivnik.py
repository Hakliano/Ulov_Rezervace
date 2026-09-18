"""P5.4 — Moderník automaticky obsahuje plný Archivník (PartnerModul)."""
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse

from archivnik.models import Customer
from flow.models import FlowUser
from partner_admin.models import MODUL_ARCHIVNIK, PartnerModul, PartnerNastaveni
from partner_admin.services import vytvor_noveho_partnera
from partner_admin.services_moduly import nastav_modul, zajisti_archivnik_pro_modernik
from rezervace.models import Zamestnanec
from rezervace.services.staff_auth import ensure_owner_flow_user
from salons.models import Salon


class Actor:
    username = 'p54-test'


class P54ModernikObsahujeArchivnikTests(TestCase):
    def setUp(self):
        self.superuser = get_user_model().objects.create_superuser(
            username='p54-admin',
            email='p54-admin@example.test',
            password='bezpecne-test-heslo',
        )
        self.client = Client()

    def _novy(self, name, email, *, flow=True):
        return vytvor_noveho_partnera(
            data={
                'name': name,
                'majitel_email': email,
                'majitel_heslo': 'DocasneHeslo99',
                'aktivovat_flow': flow,
                'tarif': 'Moderník',
            },
            actor=self.superuser,
        )

    def test_novy_modernik_partner_ma_archivnik_active(self):
        salon, _partner, _majitel, flow_user = self._novy(
            'P54 Moderník', 'p54-mod@example.test',
        )
        self.assertIsNotNone(flow_user)
        row = PartnerModul.objects.get(salon=salon, modul__kod=MODUL_ARCHIVNIK)
        self.assertEqual(row.status, PartnerModul.STAV_ACTIVE)
        self.assertEqual(
            PartnerModul.objects.filter(salon=salon, modul__kod=MODUL_ARCHIVNIK).count(),
            1,
        )

    def test_novy_partner_bez_flow_nema_auto_archivnik(self):
        salon, _p, _m, flow_user = self._novy(
            'P54 Bez FLOW', 'p54-solo-off@example.test', flow=False,
        )
        self.assertIsNone(flow_user)
        self.assertFalse(
            PartnerModul.objects.filter(
                salon=salon, modul__kod=MODUL_ARCHIVNIK, status=PartnerModul.STAV_ACTIVE,
            ).exists()
        )

    def test_aktivace_flow_zapne_archivnik(self):
        salon, _p, majitel, flow_user = self._novy(
            'P54 Později FLOW', 'p54-later@example.test', flow=False,
        )
        self.assertIsNone(flow_user)
        majitel.prihlasovaci_jmeno = 'p54-later@example.test'
        majitel.save(update_fields=['prihlasovaci_jmeno'])
        self.client.force_login(self.superuser)
        res = self.client.post(
            reverse('partner_admin:aktivovat_flow', args=[salon.id]),
            {'email': 'p54-later@example.test'},
        )
        self.assertEqual(res.status_code, 302)
        row = PartnerModul.objects.get(salon=salon, modul__kod=MODUL_ARCHIVNIK)
        self.assertEqual(row.status, PartnerModul.STAV_ACTIVE)

    def test_opakovana_aktivace_je_idempotentni(self):
        salon, _p, _m, _f = self._novy('P54 Idem', 'p54-idemp@example.test')
        pred = PartnerModul.objects.filter(salon=salon, modul__kod=MODUL_ARCHIVNIK).count()
        zajisti_archivnik_pro_modernik(salon, Actor())
        zajisti_archivnik_pro_modernik(salon, self.superuser)
        self.client.force_login(self.superuser)
        self.client.post(reverse('partner_admin:aktivovat_flow', args=[salon.id]))
        self.assertEqual(
            PartnerModul.objects.filter(salon=salon, modul__kod=MODUL_ARCHIVNIK).count(),
            pred,
        )
        self.assertEqual(pred, 1)
        row = PartnerModul.objects.get(salon=salon, modul__kod=MODUL_ARCHIVNIK)
        self.assertEqual(row.status, PartnerModul.STAV_ACTIVE)

    def test_tenant_a_neovlivni_entitlement_b(self):
        salon_a, *_ = self._novy('P54 A', 'p54-a@example.test')
        salon_b = Salon.objects.create(name='P54 B', email='p54-b@example.test')
        Zamestnanec.objects.create(
            salon=salon_b,
            jmeno='Majitel B',
            role=Zamestnanec.ROLE_MAJITEL,
            prihlasovaci_jmeno='p54-b@example.test',
            aktivni=True,
        )
        self.assertTrue(
            PartnerModul.objects.filter(
                salon=salon_a, modul__kod=MODUL_ARCHIVNIK, status=PartnerModul.STAV_ACTIVE,
            ).exists()
        )
        self.assertFalse(
            PartnerModul.objects.filter(salon=salon_b, modul__kod=MODUL_ARCHIVNIK).exists()
        )

    def test_standalone_bez_modernika_a_flow(self):
        salon = Salon.objects.create(name='P54 Solo', email='p54-solo@example.test')
        owner = Zamestnanec.objects.create(
            salon=salon,
            jmeno='Sólo',
            role=Zamestnanec.ROLE_MAJITEL,
            prihlasovaci_jmeno='p54-solo@example.test',
            aktivni=True,
        )
        owner.set_password('archivnik123')
        owner.save(update_fields=['password_hash'])
        nastav_modul(salon, MODUL_ARCHIVNIK, True, Actor())
        self.assertFalse(FlowUser.objects.filter(salon=salon).exists())
        login = self.client.post(
            '/api/archivnik/auth/login/',
            {'email': 'p54-solo@example.test', 'password': 'archivnik123'},
            content_type='application/json',
        )
        self.assertEqual(login.status_code, 200)
        token = login.json()['token']
        seznam = self.client.get(
            '/api/archivnik/customers/', HTTP_X_ARCHIVNIK_TOKEN=token,
        )
        self.assertEqual(seznam.status_code, 200)

    def test_smazani_flow_uctu_nemaže_archivnik_ani_data(self):
        salon, _p, _m, flow_user = self._novy('P54 Off', 'p54-off@example.test')
        zak = Customer.objects.create(salon=salon, prijmeni='Novák', jmeno='Jan')
        FlowUser.objects.filter(pk=flow_user.pk).delete()
        self.assertFalse(FlowUser.objects.filter(salon=salon).exists())
        row = PartnerModul.objects.get(salon=salon, modul__kod=MODUL_ARCHIVNIK)
        self.assertEqual(row.status, PartnerModul.STAV_ACTIVE)
        self.assertTrue(Customer.objects.filter(pk=zak.pk).exists())
        partner = salon.partner_nastaveni
        partner.stav = PartnerNastaveni.STAV_BLOCKED
        partner.save(update_fields=['stav'])
        self.assertTrue(Customer.objects.filter(pk=zak.pk).exists())
        nastav_modul(salon, MODUL_ARCHIVNIK, False, Actor())
        self.assertTrue(Customer.objects.filter(pk=zak.pk).exists())
        row.refresh_from_db()
        self.assertEqual(row.status, PartnerModul.STAV_INACTIVE)

    def test_sync_command_zapne_jen_flow_partnery(self):
        flow_salon, *_ = self._novy('P54 Sync FLOW', 'p54-sync-flow@example.test')
        PartnerModul.objects.filter(
            salon=flow_salon, modul__kod=MODUL_ARCHIVNIK,
        ).update(status=PartnerModul.STAV_INACTIVE)
        solo = Salon.objects.create(name='P54 Sync Solo', email='p54-sync-solo@example.test')
        call_command('sync_archivnik_pro_modernik')
        self.assertTrue(
            PartnerModul.objects.filter(
                salon=flow_salon, modul__kod=MODUL_ARCHIVNIK, status=PartnerModul.STAV_ACTIVE,
            ).exists()
        )
        self.assertFalse(
            PartnerModul.objects.filter(salon=solo, modul__kod=MODUL_ARCHIVNIK).exists()
        )

    def test_ensure_owner_flow_user_pri_vytvoreni_zapne_archivnik(self):
        salon = Salon.objects.create(name='P54 Ensure', email='p54-ensure@example.test')
        owner = Zamestnanec.objects.create(
            salon=salon,
            jmeno='Majitelka',
            role=Zamestnanec.ROLE_MAJITEL,
            prihlasovaci_jmeno='p54-ensure@example.test',
            aktivni=True,
        )
        owner.set_password('Heslo1234')
        owner.save(update_fields=['password_hash'])
        _user, created = ensure_owner_flow_user(salon)
        self.assertTrue(created)
        self.assertTrue(
            PartnerModul.objects.filter(
                salon=salon, modul__kod=MODUL_ARCHIVNIK, status=PartnerModul.STAV_ACTIVE,
            ).exists()
        )
        _user2, created2 = ensure_owner_flow_user(salon)
        self.assertFalse(created2)
        self.assertEqual(
            PartnerModul.objects.filter(salon=salon, modul__kod=MODUL_ARCHIVNIK).count(),
            1,
        )
