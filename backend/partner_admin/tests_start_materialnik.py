"""Etapa 4 — Materiálník START/PRO a individuální grant."""
from datetime import timedelta
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from partner_admin.entitlements import (
    FEATURE_ARCHIVNIK,
    FEATURE_EXTRA_STAFF,
    FEATURE_IMAP,
    FEATURE_KARTOTEKA,
    FEATURE_MATERIALNIK,
    FEATURE_STATS,
    ModulNeniVNaroku,
    kartoteka_smí_fungovat,
    materialnik_smí_fungovat,
    partner_ma,
)
from partner_admin.models import (
    MODUL_ARCHIVNIK,
    MODUL_MATERIALNIK,
    PartnerFeatureGrant,
    PartnerModul,
    PartnerNastaveni,
)
from partner_admin.services import vytvor_noveho_partnera
from partner_admin.services_moduly import (
    archivnik_je_aktivni,
    nastav_modul,
    odeber_materialnik_grant,
    povol_materialnik_individulne,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


class Actor:
    username = 'e4-admin'


@override_settings(MATERIALNIK_STUB=True, MATERIALNIK_M2M_KEY='test-m2m')
class StartMaterialnikTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_superuser(
            username='e4-admin',
            email='e4-admin@example.test',
            password='bezpecne-test-heslo',
        )
        self.client = Client()

    def _novy(self, name, email, *, plan=PartnerNastaveni.PLAN_START):
        return vytvor_noveho_partnera(
            data={
                'name': name,
                'majitel_email': email,
                'majitel_heslo': 'DocasneHeslo99',
                'aktivovat_flow': True,
                'plan': plan,
                'tarif': 'Moderník',
            },
            actor=self.actor,
        )

    def _flow_token(self, email, password='DocasneHeslo99'):
        r = self.client.post(
            '/api/flow/prihlaseni/',
            data={'email': email, 'password': password},
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()['token']

    def _session(self, email, password='DocasneHeslo99'):
        return self.client.post(
            '/api/integrations/v1/materialnik/session',
            data={'email': email, 'password': password},
            content_type='application/json',
            HTTP_X_ULOV_M2M_KEY='test-m2m',
        )

    def test_start_bez_grantu_materialnik_off(self):
        salon, partner, _m, _f = self._novy('E4 START', 'e4-start@example.test')
        self.assertEqual(partner.plan, PartnerNastaveni.PLAN_START)
        self.assertFalse(partner_ma(salon, FEATURE_MATERIALNIK))
        self.assertFalse(materialnik_smí_fungovat(salon))
        with self.assertRaises(ModulNeniVNaroku):
            nastav_modul(salon, MODUL_MATERIALNIK, True, Actor())
        token = self._flow_token('e4-start@example.test')
        me = self.client.get('/api/flow/me/', HTTP_X_FLOW_TOKEN=token)
        self.assertNotIn('materialnik', me.json().get('moduly') or {})
        self.assertEqual(self._session('e4-start@example.test').status_code, 401)
        prehled = self.client.get(
            '/api/flow/materialnik-prehled/', HTTP_X_FLOW_TOKEN=token,
        )
        self.assertEqual(prehled.status_code, 404)
        self.client.force_login(self.actor)
        zap = self.client.post(
            reverse('partner_admin:nastavit_materialnik', args=[salon.id]),
            {'zapnout': '1'},
        )
        self.assertEqual(zap.status_code, 302)
        self.assertFalse(materialnik_smí_fungovat(salon))

    def test_start_grant_active_funguje_a_zustava_start(self):
        salon, partner, _m, _f = self._novy('E4 Grant', 'e4-grant@example.test')
        tenant = partner.tenant_uuid
        self.client.force_login(self.actor)
        pov = self.client.post(
            reverse('partner_admin:nastavit_materialnik', args=[salon.id]),
            {'akce': 'povolit'},
        )
        self.assertEqual(pov.status_code, 302)
        partner.refresh_from_db()
        self.assertEqual(partner.plan, PartnerNastaveni.PLAN_START)
        self.assertEqual(partner.tenant_uuid, tenant)
        self.assertTrue(partner_ma(salon, FEATURE_MATERIALNIK))
        self.assertTrue(materialnik_smí_fungovat(salon))
        self.assertFalse(partner_ma(salon, FEATURE_ARCHIVNIK))
        self.assertFalse(partner_ma(salon, FEATURE_KARTOTEKA))
        self.assertFalse(partner_ma(salon, FEATURE_EXTRA_STAFF))
        self.assertFalse(partner_ma(salon, FEATURE_IMAP))
        self.assertFalse(partner_ma(salon, FEATURE_STATS))
        self.assertFalse(kartoteka_smí_fungovat(salon))
        self.assertFalse(archivnik_je_aktivni(salon))

        token = self._flow_token('e4-grant@example.test')
        with self.settings(MATERIALNIK_PUBLIC_URL='http://127.0.0.1:8001'):
            me = self.client.get('/api/flow/me/', HTTP_X_FLOW_TOKEN=token)
        self.assertEqual(me.json()['moduly']['materialnik']['url'], 'http://127.0.0.1:8001')
        self.assertEqual(self._session('e4-grant@example.test').status_code, 200)
        prehled = self.client.get(
            '/api/flow/materialnik-prehled/', HTTP_X_FLOW_TOKEN=token,
        )
        self.assertEqual(prehled.status_code, 200)
        detail = self.client.get(reverse('partner_admin:detail', args=[salon.id]))
        self.assertContains(detail, 'Individuálně povolený modul')
        self.assertContains(detail, 'Odebrat nárok ze START')

    def test_start_grant_inactive_neni_dostupny_data_zustavaji(self):
        salon, partner, _m, _f = self._novy('E4 Off', 'e4-off@example.test')
        povol_materialnik_individulne(salon, Actor())
        tenant = partner.tenant_uuid
        hmac = PartnerModul.objects.get(salon=salon, modul__kod=MODUL_MATERIALNIK).hmac_key
        nastav_modul(salon, MODUL_MATERIALNIK, False, Actor())
        self.assertTrue(partner_ma(salon, FEATURE_MATERIALNIK))
        self.assertFalse(materialnik_smí_fungovat(salon))
        token = self._flow_token('e4-off@example.test')
        me = self.client.get('/api/flow/me/', HTTP_X_FLOW_TOKEN=token)
        self.assertNotIn('materialnik', me.json().get('moduly') or {})
        self.assertEqual(self._session('e4-off@example.test').status_code, 401)
        partner.refresh_from_db()
        self.assertEqual(partner.tenant_uuid, tenant)
        row = PartnerModul.objects.get(salon=salon, modul__kod=MODUL_MATERIALNIK)
        self.assertEqual(row.hmac_key, hmac)
        self.assertEqual(row.status, PartnerModul.STAV_INACTIVE)

    def test_expirovany_grant_odmitne_session_i_flow(self):
        salon, partner, _m, _f = self._novy('E4 Exp', 'e4-exp@example.test')
        povol_materialnik_individulne(salon, Actor())
        grant = PartnerFeatureGrant.objects.get(
            salon=salon, feature=FEATURE_MATERIALNIK, zakaz=False, aktivni=True,
        )
        grant.platnost_do = timezone.now() - timedelta(days=1)
        grant.save(update_fields=['platnost_do', 'aktualizovano'])
        self.assertFalse(partner_ma(salon, FEATURE_MATERIALNIK))
        token = self._flow_token('e4-exp@example.test')
        me = self.client.get('/api/flow/me/', HTTP_X_FLOW_TOKEN=token)
        self.assertNotIn('materialnik', me.json().get('moduly') or {})
        self.assertEqual(self._session('e4-exp@example.test').status_code, 401)
        self.assertFalse(materialnik_smí_fungovat(salon))
        partner.refresh_from_db()
        self.assertTrue(partner.tenant_uuid)
        self.assertTrue(
            PartnerFeatureGrant.objects.filter(
                salon=salon, feature=FEATURE_MATERIALNIK, aktivni=True,
            ).exists()
        )

    def test_odebrany_grant_odmitne_pristup_nemaže_data(self):
        salon, partner, _m, _f = self._novy('E4 Rev', 'e4-rev@example.test')
        povol_materialnik_individulne(salon, Actor())
        tenant = partner.tenant_uuid
        odeber_materialnik_grant(salon, Actor())
        self.assertFalse(partner_ma(salon, FEATURE_MATERIALNIK))
        self.assertFalse(materialnik_smí_fungovat(salon))
        self.assertEqual(self._session('e4-rev@example.test').status_code, 401)
        partner.refresh_from_db()
        self.assertEqual(partner.tenant_uuid, tenant)
        self.assertEqual(partner.plan, PartnerNastaveni.PLAN_START)

    def test_pro_on_off_on_bez_grantu(self):
        salon, partner, _m, _f = self._novy(
            'E4 PRO', 'e4-pro@example.test', plan=PartnerNastaveni.PLAN_PRO,
        )
        self.assertTrue(materialnik_smí_fungovat(salon))
        self.assertFalse(
            PartnerFeatureGrant.objects.filter(
                salon=salon, feature=FEATURE_MATERIALNIK,
            ).exists()
        )
        tenant = partner.tenant_uuid
        token = self._flow_token('e4-pro@example.test')
        self.assertEqual(self._session('e4-pro@example.test').status_code, 200)
        nastav_modul(salon, MODUL_MATERIALNIK, False, Actor())
        partner.refresh_from_db()
        self.assertEqual(partner.plan, PartnerNastaveni.PLAN_PRO)
        self.assertTrue(partner_ma(salon, FEATURE_EXTRA_STAFF))
        self.assertFalse(materialnik_smí_fungovat(salon))
        me = self.client.get('/api/flow/me/', HTTP_X_FLOW_TOKEN=token)
        self.assertNotIn('materialnik', me.json().get('moduly') or {})
        nastav_modul(salon, MODUL_MATERIALNIK, True, Actor())
        self.assertTrue(materialnik_smí_fungovat(salon))
        partner.refresh_from_db()
        self.assertEqual(partner.tenant_uuid, tenant)
        self.assertEqual(self._session('e4-pro@example.test').status_code, 200)

    def test_pro_na_start_bez_grantu_znepristupni(self):
        salon, partner, _m, _f = self._novy(
            'E4 Down', 'e4-down@example.test', plan=PartnerNastaveni.PLAN_PRO,
        )
        tenant = partner.tenant_uuid
        self.assertTrue(materialnik_smí_fungovat(salon))
        partner.plan = PartnerNastaveni.PLAN_START
        partner.save()
        partner.refresh_from_db()
        self.assertEqual(partner.plan, PartnerNastaveni.PLAN_START)
        self.assertFalse(partner_ma(salon, FEATURE_MATERIALNIK))
        self.assertFalse(materialnik_smí_fungovat(salon))
        self.assertEqual(partner.tenant_uuid, tenant)
        self.assertEqual(self._session('e4-down@example.test').status_code, 401)

    def test_start_na_pro_entitlement_z_planu(self):
        salon, partner, _m, _f = self._novy('E4 Up', 'e4-up@example.test')
        povol_materialnik_individulne(salon, Actor())
        tenant = partner.tenant_uuid
        partner.plan = PartnerNastaveni.PLAN_PRO
        partner.save()
        partner.refresh_from_db()
        self.assertEqual(partner.plan, PartnerNastaveni.PLAN_PRO)
        self.assertTrue(partner_ma(salon, FEATURE_MATERIALNIK))
        self.assertEqual(partner.tenant_uuid, tenant)
        nastav_modul(salon, MODUL_MATERIALNIK, True, Actor())
        self.assertTrue(materialnik_smí_fungovat(salon))
        self.assertEqual(self._session('e4-up@example.test').status_code, 200)

    def test_moduly_jsou_nezavisle(self):
        salon, _p, _m, _f = self._novy(
            'E4 Mix', 'e4-mix@example.test', plan=PartnerNastaveni.PLAN_PRO,
        )
        nastav_modul(salon, MODUL_MATERIALNIK, False, Actor())
        self.assertTrue(archivnik_je_aktivni(salon))
        self.assertTrue(kartoteka_smí_fungovat(salon))
        self.assertFalse(materialnik_smí_fungovat(salon))
        nastav_modul(salon, MODUL_MATERIALNIK, True, Actor())
        nastav_modul(salon, MODUL_ARCHIVNIK, False, Actor())
        self.assertTrue(materialnik_smí_fungovat(salon))
        self.assertFalse(archivnik_je_aktivni(salon))
        self.assertFalse(kartoteka_smí_fungovat(salon))

        start, sp, *_ = self._novy('E4 Mix START', 'e4-mix-s@example.test')
        povol_materialnik_individulne(start, Actor())
        self.assertEqual(sp.plan, PartnerNastaveni.PLAN_START)
        self.assertTrue(materialnik_smí_fungovat(start))
        self.assertFalse(archivnik_je_aktivni(start))
        self.assertFalse(kartoteka_smí_fungovat(start))

    def test_partner_admin_start_ukazuje_povolit(self):
        salon, *_ = self._novy('E4 UI', 'e4-ui@example.test')
        self.client.force_login(self.actor)
        detail = self.client.get(reverse('partner_admin:detail', args=[salon.id]))
        self.assertContains(detail, 'Není součástí plánu START')
        self.assertContains(detail, 'Povolit Materiálník')
        self.assertNotContains(detail, 'Součást plánu PRO')
        self.assertNotContains(detail, 'Zapnout Archivník')

    def test_partner_admin_pro_ukazuje_soucast_planu(self):
        salon, *_ = self._novy(
            'E4 UI PRO', 'e4-ui-pro@example.test', plan=PartnerNastaveni.PLAN_PRO,
        )
        self.client.force_login(self.actor)
        detail = self.client.get(reverse('partner_admin:detail', args=[salon.id]))
        self.assertContains(detail, 'Součást plánu PRO')
        self.assertContains(detail, 'Vypnout Materiálník')

    def test_flow_ui_stale_ridi_moduly_materialnik(self):
        app = (REPO_ROOT / 'flow' / 'app.js').read_text(encoding='utf-8')
        self.assertIn('function applyMaterialnikUi', app)
        self.assertIn('user?.moduly?.materialnik', app)
