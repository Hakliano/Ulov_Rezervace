"""Etapa 1 — produktový plán START/PRO a centrální entitlement vrstva."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from partner_admin.entitlements import (
    FEATURE_ARCHIVNIK,
    FEATURE_EXTRA_STAFF,
    FEATURE_IMAP,
    FEATURE_KARTOTEKA,
    FEATURE_MATERIALNIK,
    FEATURE_NOSHOW_ARCHIVE,
    FEATURE_POST_VISIT_EMAIL,
    FEATURE_STATS,
    FEATURES,
    ModulNeniVNaroku,
    NeznamaFeature,
    kartoteka_smí_fungovat,
    partner_ma,
    plan_partnera,
)
from partner_admin.models import (
    MODUL_ARCHIVNIK,
    MODUL_MATERIALNIK,
    PartnerFeatureGrant,
    PartnerModul,
    PartnerNastaveni,
)
from partner_admin.services import vytvor_noveho_partnera
from partner_admin.services_moduly import nastav_modul, zajisti_archivnik_pro_modernik
from rezervace.services.staff_auth import ensure_owner_flow_user
from salons.models import Salon


class Actor:
    username = 'e1-test'


@override_settings(MATERIALNIK_STUB=True)
class EntitlementPlanTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_superuser(
            username='e1-admin',
            email='e1-admin@example.test',
            password='bezpecne-test-heslo',
        )

    def _novy(self, name, email, *, plan=PartnerNastaveni.PLAN_PRO, flow=True, tarif='Moderník'):
        return vytvor_noveho_partnera(
            data={
                'name': name,
                'majitel_email': email,
                'majitel_heslo': 'DocasneHeslo99',
                'aktivovat_flow': flow,
                'plan': plan,
                'tarif': tarif,
                'castka': '1590.00',
            },
            actor=self.actor,
        )

    def test_existujici_salon_dostane_plan_pro_a_tarif_se_nemeni(self):
        salon = Salon.objects.create(name='E1 Demo', email='e1-demo@example.test')
        partner = salon.partner_nastaveni
        partner.tarif = 'Partner pro váš salon'
        partner.castka = 499
        partner.save()
        partner.refresh_from_db()
        self.assertEqual(partner.plan, PartnerNastaveni.PLAN_PRO)
        self.assertEqual(partner.tarif, 'Partner pro váš salon')
        self.assertEqual(partner.castka, 499)
        for feature in FEATURES:
            self.assertTrue(partner_ma(salon, feature), feature)

    def test_start_nema_pro_features_ale_ma_flow(self):
        salon, partner, majitel, flow_user = self._novy(
            'E1 START', 'e1-start@example.test', plan=PartnerNastaveni.PLAN_START,
        )
        self.assertEqual(partner.plan, PartnerNastaveni.PLAN_START)
        self.assertEqual(partner.tarif, 'Moderník')
        self.assertIsNotNone(flow_user)
        self.assertTrue(hasattr(majitel, 'flow_ucet'))
        for feature in FEATURES:
            self.assertFalse(partner_ma(salon, feature), feature)
        self.assertFalse(
            PartnerModul.objects.filter(
                salon=salon, modul__kod=MODUL_ARCHIVNIK, status=PartnerModul.STAV_ACTIVE,
            ).exists()
        )
        self.assertFalse(
            PartnerModul.objects.filter(
                salon=salon, modul__kod=MODUL_MATERIALNIK, status=PartnerModul.STAV_ACTIVE,
            ).exists()
        )

    def test_pro_ma_vsechny_features_prvni_vlny(self):
        salon, partner, _m, flow_user = self._novy('E1 PRO', 'e1-pro@example.test')
        self.assertEqual(partner.plan, PartnerNastaveni.PLAN_PRO)
        self.assertIsNotNone(flow_user)
        for feature in FEATURES:
            self.assertTrue(partner_ma(salon, feature), feature)
        self.assertTrue(
            PartnerModul.objects.filter(
                salon=salon, modul__kod=MODUL_ARCHIVNIK, status=PartnerModul.STAV_ACTIVE,
            ).exists()
        )
        self.assertTrue(
            PartnerModul.objects.filter(
                salon=salon, modul__kod=MODUL_MATERIALNIK, status=PartnerModul.STAV_ACTIVE,
            ).exists()
        )

    def test_plan_je_oddelen_od_tarifu(self):
        salon, partner, *_ = self._novy(
            'E1 Mix',
            'e1-mix@example.test',
            plan=PartnerNastaveni.PLAN_START,
            tarif='Moderník + Materiálník + Archivník',
        )
        self.assertEqual(partner.plan, PartnerNastaveni.PLAN_START)
        self.assertEqual(partner.tarif, 'Moderník + Materiálník + Archivník')
        self.assertFalse(partner_ma(salon, FEATURE_ARCHIVNIK))
        self.assertFalse(partner_ma(salon, FEATURE_MATERIALNIK))

    def test_neznama_feature_vyhodi_chybu(self):
        salon = Salon.objects.create(name='E1 Unknown', email='e1-unk@example.test')
        with self.assertRaises(NeznamaFeature):
            partner_ma(salon, 'nfc')
        with self.assertRaises(NeznamaFeature):
            partner_ma(salon, 'waitlist')

    def test_start_nemuze_aktivovat_moduly(self):
        salon, *_ = self._novy(
            'E1 Start lock', 'e1-lock@example.test', plan=PartnerNastaveni.PLAN_START,
        )
        with self.assertRaises(ModulNeniVNaroku):
            nastav_modul(salon, MODUL_ARCHIVNIK, True, Actor())
        with self.assertRaises(ModulNeniVNaroku):
            nastav_modul(salon, MODUL_MATERIALNIK, True, Actor())
        self.assertFalse(
            PartnerModul.objects.filter(salon=salon, modul__kod=MODUL_ARCHIVNIK).exists()
        )

    def test_pro_muze_vypnout_modul_bez_zmeny_planu_a_dat(self):
        from archivnik.models import Customer

        salon, partner, *_ = self._novy('E1 Off', 'e1-off@example.test')
        zak = Customer.objects.create(salon=salon, prijmeni='Novák', jmeno='Jan')
        tarif = partner.tarif
        castka = partner.castka
        nastav_modul(salon, MODUL_ARCHIVNIK, False, Actor())
        partner.refresh_from_db()
        self.assertEqual(partner.plan, PartnerNastaveni.PLAN_PRO)
        self.assertEqual(partner.tarif, tarif)
        self.assertEqual(partner.castka, castka)
        self.assertTrue(partner_ma(salon, FEATURE_ARCHIVNIK))
        self.assertTrue(partner_ma(salon, FEATURE_MATERIALNIK))
        self.assertTrue(partner_ma(salon, FEATURE_KARTOTEKA))
        self.assertFalse(kartoteka_smí_fungovat(salon))
        self.assertTrue(Customer.objects.filter(pk=zak.pk).exists())
        row = PartnerModul.objects.get(salon=salon, modul__kod=MODUL_ARCHIVNIK)
        self.assertEqual(row.status, PartnerModul.STAV_INACTIVE)
        nastav_modul(salon, MODUL_ARCHIVNIK, True, Actor())
        self.assertTrue(kartoteka_smí_fungovat(salon))
        self.assertTrue(Customer.objects.filter(pk=zak.pk).exists())

    def test_flow_u_startu_nezapne_archivnik(self):
        salon, _p, majitel, flow_user = self._novy(
            'E1 Flow START', 'e1-flow-start@example.test',
            plan=PartnerNastaveni.PLAN_START, flow=False,
        )
        self.assertIsNone(flow_user)
        majitel.prihlasovaci_jmeno = 'e1-flow-start@example.test'
        majitel.save(update_fields=['prihlasovaci_jmeno'])
        user, created = ensure_owner_flow_user(salon, email='e1-flow-start@example.test')
        self.assertEqual(user.email, 'e1-flow-start@example.test')
        self.assertFalse(
            PartnerModul.objects.filter(
                salon=salon, modul__kod=MODUL_ARCHIVNIK, status=PartnerModul.STAV_ACTIVE,
            ).exists()
        )
        zajisti_archivnik_pro_modernik(salon, Actor())
        self.assertFalse(
            PartnerModul.objects.filter(
                salon=salon, modul__kod=MODUL_ARCHIVNIK, status=PartnerModul.STAV_ACTIVE,
            ).exists()
        )

    def test_sync_respektuje_entitlement_a_vypnuti(self):
        start, *_ = self._novy(
            'E1 Sync START', 'e1-sync-start@example.test', plan=PartnerNastaveni.PLAN_START,
        )
        pro, *_ = self._novy('E1 Sync PRO', 'e1-sync-pro@example.test')
        PartnerModul.objects.filter(
            salon=pro, modul__kod=MODUL_ARCHIVNIK,
        ).update(status=PartnerModul.STAV_INACTIVE)
        call_command('sync_archivnik_pro_modernik')
        self.assertFalse(
            PartnerModul.objects.filter(
                salon=start, modul__kod=MODUL_ARCHIVNIK, status=PartnerModul.STAV_ACTIVE,
            ).exists()
        )
        self.assertTrue(
            PartnerModul.objects.filter(
                salon=pro, modul__kod=MODUL_ARCHIVNIK, status=PartnerModul.STAV_INACTIVE,
            ).exists()
        )

    def test_grant_da_startu_jednu_feature(self):
        salon, *_ = self._novy(
            'E1 Grant', 'e1-grant@example.test', plan=PartnerNastaveni.PLAN_START,
        )
        self.assertFalse(partner_ma(salon, FEATURE_ARCHIVNIK))
        PartnerFeatureGrant.objects.create(
            salon=salon,
            feature=FEATURE_ARCHIVNIK,
            zdroj=PartnerFeatureGrant.ZDROJ_TRIAL,
        )
        self.assertTrue(partner_ma(salon, FEATURE_ARCHIVNIK))
        self.assertFalse(partner_ma(salon, FEATURE_MATERIALNIK))
        nastav_modul(salon, MODUL_ARCHIVNIK, True, Actor())
        self.assertTrue(
            PartnerModul.objects.filter(
                salon=salon, modul__kod=MODUL_ARCHIVNIK, status=PartnerModul.STAV_ACTIVE,
            ).exists()
        )

    def test_expirovany_grant_neplati(self):
        salon, *_ = self._novy(
            'E1 Exp', 'e1-exp@example.test', plan=PartnerNastaveni.PLAN_START,
        )
        ted = timezone.now()
        PartnerFeatureGrant.objects.create(
            salon=salon,
            feature=FEATURE_IMAP,
            platnost_od=ted - timedelta(days=40),
            platnost_do=ted - timedelta(days=10),
            zdroj=PartnerFeatureGrant.ZDROJ_TRIAL,
        )
        self.assertFalse(partner_ma(salon, FEATURE_IMAP))

    def test_zakaz_prebije_plan_pro(self):
        salon, *_ = self._novy('E1 Deny', 'e1-deny@example.test')
        self.assertTrue(partner_ma(salon, FEATURE_EXTRA_STAFF))
        PartnerFeatureGrant.objects.create(
            salon=salon,
            feature=FEATURE_EXTRA_STAFF,
            zakaz=True,
            zdroj=PartnerFeatureGrant.ZDROJ_VYJIMKA,
        )
        self.assertFalse(partner_ma(salon, FEATURE_EXTRA_STAFF))
        self.assertTrue(partner_ma(salon, FEATURE_STATS))

    def test_partner_admin_odmitne_zapnout_archivnik_u_startu(self):
        salon, *_ = self._novy(
            'E1 UI START', 'e1-ui-start@example.test', plan=PartnerNastaveni.PLAN_START,
        )
        self.client.force_login(self.actor)
        res = self.client.post(
            reverse('partner_admin:nastavit_archivnik', args=[salon.id]),
            {'zapnout': '1'},
        )
        self.assertEqual(res.status_code, 302)
        self.assertFalse(
            PartnerModul.objects.filter(
                salon=salon, modul__kod=MODUL_ARCHIVNIK, status=PartnerModul.STAV_ACTIVE,
            ).exists()
        )

    def test_kartoteka_entitlement_nestačí_bez_archivniku(self):
        salon, *_ = self._novy('E1 Kart', 'e1-kart@example.test')
        self.assertTrue(partner_ma(salon, FEATURE_KARTOTEKA))
        self.assertTrue(kartoteka_smí_fungovat(salon))
        nastav_modul(salon, MODUL_ARCHIVNIK, False, Actor())
        self.assertTrue(partner_ma(salon, FEATURE_KARTOTEKA))
        self.assertFalse(kartoteka_smí_fungovat(salon))

    def test_noshow_archive_a_post_visit_jsou_pro(self):
        start, *_ = self._novy(
            'E1 NS', 'e1-ns@example.test', plan=PartnerNastaveni.PLAN_START,
        )
        pro, *_ = self._novy('E1 NS PRO', 'e1-ns-pro@example.test')
        self.assertFalse(partner_ma(start, FEATURE_NOSHOW_ARCHIVE))
        self.assertFalse(partner_ma(start, FEATURE_POST_VISIT_EMAIL))
        self.assertTrue(partner_ma(pro, FEATURE_NOSHOW_ARCHIVE))
        self.assertTrue(partner_ma(pro, FEATURE_POST_VISIT_EMAIL))

    def test_plan_partnera_prazdny_je_pro(self):
        salon = Salon.objects.create(name='E1 Empty', email='e1-empty@example.test')
        PartnerNastaveni.objects.filter(salon=salon).update(plan='')
        salon.partner_nastaveni.refresh_from_db()
        self.assertEqual(plan_partnera(salon), PartnerNastaveni.PLAN_PRO)
        self.assertTrue(partner_ma(salon, FEATURE_ARCHIVNIK))
