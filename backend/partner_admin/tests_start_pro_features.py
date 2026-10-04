"""Etapa 5 — zbývající PRO funkce přes partner_ma(), bez plan==pro."""
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from flow.mail_service import get_imap_config
from flow.persona_service import set_majitelka_pracuje
from partner_admin.entitlements import (
    FEATURE_AUDIT,
    FEATURE_IMAP,
    FEATURE_NOSHOW_ARCHIVE,
    FEATURE_POST_VISIT_EMAIL,
    FEATURE_STATS,
    FEATURE_TECH_SETTINGS,
    MSG_FUNKCE_NEDOSTUPNA,
    partner_ma,
)
from partner_admin.models import PartnerFeatureGrant, PartnerNastaveni
from partner_admin.services import vytvor_noveho_partnera
from partner_admin.staff_limits import pracovni_persona_managera
from rezervace.models import (
    Rezervace,
    RezervacniNastaveni,
    SalonAuditLog,
    ZamestnanecSession,
    ZamestnanecSluzba,
)
from rezervace.notifikace_defaults import vychozi_notifikace
from rezervace.services.emails import email_potvrzeni, email_storno
from rezervace.services.gdpr import dekujici_notifikace_aktivni
from rezervace.services.zivotni_cyklus import _odeslat_planovane_emaily
from salons.models import CenikPolozka


@override_settings(MATERIALNIK_STUB=True)
class StartProFeaturesTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_superuser(
            username='e5-admin',
            email='e5-admin@example.test',
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

    def _h(self, token):
        return {'HTTP_X_FLOW_TOKEN': token}

    def _zapni_tech_flag(self, salon):
        PartnerNastaveni.objects.filter(salon=salon).update(
            povolit_technicke_nastaveni=True,
        )

    def _nastaveni(self, salon, **extra):
        nast, _ = RezervacniNastaveni.objects.get_or_create(salon=salon)
        nast.notifikace = vychozi_notifikace()
        nast.imap_enabled = True
        nast.imap_host = 'imap.example.test'
        for key, val in extra.items():
            setattr(nast, key, val)
        nast.save()
        return nast

    def _rezervace(self, salon, *, stav='potvrzeno', zacatek=None, konec=None, email='host@e5.test'):
        now = timezone.now()
        pz = pracovni_persona_managera(salon)
        if pz is None:
            set_majitelka_pracuje(salon, ano=True, jmeno='Marie E5')
            pz = pracovni_persona_managera(salon)
        sluzba = CenikPolozka.objects.filter(salon=salon).first()
        if sluzba is None:
            sluzba = CenikPolozka.objects.create(
                salon=salon, nazev='Střih E5', cena=400, delka_minut=30, aktivni=True,
            )
            ZamestnanecSluzba.objects.get_or_create(zamestnanec=pz, sluzba=sluzba)
        zacatek = zacatek or (now + timedelta(hours=24))
        konec = konec or (zacatek + timedelta(minutes=30))
        return Rezervace.objects.create(
            salon=salon,
            zamestnanec=pz,
            zacatek=zacatek,
            konec=konec,
            stav=stav,
            jmeno_host='Host E5',
            email_host=email,
        )

    def test_start_me_nema_pro_flagy_ale_ma_flow(self):
        salon, partner, _m, _f = self._novy('E5 START me', 'e5-start-me@example.test')
        token = self._flow_token('e5-start-me@example.test')
        me = self.client.get('/api/flow/me/', **self._h(token)).json()
        self.assertEqual(me['plan'], PartnerNastaveni.PLAN_START)
        for kod in (
            'imap', 'post_visit_email', 'stats', 'audit',
            'tech_settings', 'noshow_archive',
        ):
            self.assertFalse(me[kod], kod)
        kal = self.client.get('/api/flow/kalendar/', **self._h(token))
        self.assertEqual(kal.status_code, 200)

    def test_start_imap_stats_audit_tech_noshow_archiv_403(self):
        salon, _p, _m, _f = self._novy('E5 START lock', 'e5-lock@example.test')
        self._zapni_tech_flag(salon)
        self._nastaveni(salon)
        token = self._flow_token('e5-lock@example.test')
        h = self._h(token)
        paths = [
            '/api/flow/mail/stav/',
            '/api/flow/mail/',
            '/api/flow/mail/odeslane/',
            '/api/flow/owner/statistiky/',
            '/api/flow/owner/audit-log/',
            '/api/flow/owner/nastaveni/',
            '/api/flow/owner/no-show-archiv/',
        ]
        for path in paths:
            r = self.client.get(path, **h)
            self.assertEqual(r.status_code, 403, path)
            self.assertEqual(r.json()['detail'], MSG_FUNKCE_NEDOSTUPNA)
        odeslat = self.client.post(
            '/api/flow/mail/odeslat/',
            data={'to': 'a@b.test', 'subject': 'x', 'body': 'y'},
            content_type='application/json',
            **h,
        )
        self.assertEqual(odeslat.status_code, 403)
        blok = self.client.post(
            '/api/flow/owner/no-show-blokovat/',
            data={'email': 'x@e5.test'},
            content_type='application/json',
            **h,
        )
        self.assertEqual(blok.status_code, 403)
        cfg = get_imap_config(salon)
        self.assertFalse(cfg['enabled'])
        self.assertFalse(cfg['ready'])
        nast = RezervacniNastaveni.objects.get(salon=salon)
        self.assertTrue(nast.imap_enabled)
        self.assertEqual(nast.imap_host, 'imap.example.test')

    def test_start_zakladni_noshow_a_kalendar_funguji(self):
        salon, _p, _m, _f = self._novy('E5 START ops', 'e5-ops@example.test')
        rez = self._rezervace(salon)
        token = self._flow_token('e5-ops@example.test')
        h = self._h(token)
        kal = self.client.get('/api/flow/kalendar/', **h)
        self.assertEqual(kal.status_code, 200)
        noshow = self.client.post(
            f'/api/flow/rezervace/{rez.id}/noshow/',
            data={},
            content_type='application/json',
            **h,
        )
        self.assertEqual(noshow.status_code, 200, noshow.content)
        rez.refresh_from_db()
        self.assertEqual(rez.stav, 'no_show')
        archiv = self.client.get('/api/flow/owner/no-show-archiv/', **h)
        self.assertEqual(archiv.status_code, 403)

    def test_start_smtp_potvrzeni_pripominka_storno_bez_post_visit(self):
        salon, _p, _m, _f = self._novy('E5 START mail', 'e5-mail@example.test')
        self._nastaveni(salon)
        now = timezone.now()
        rez_potvrzeni = self._rezervace(
            salon, stav='potvrzeno',
            zacatek=now + timedelta(hours=24),
            email='potvrzeni@e5.test',
        )
        rez_dekuji = self._rezervace(
            salon, stav='dokonceno',
            zacatek=now - timedelta(hours=3),
            konec=now - timedelta(hours=2),
            email='dekuji@e5.test',
        )
        self.assertFalse(partner_ma(salon, FEATURE_POST_VISIT_EMAIL))
        self.assertFalse(dekujici_notifikace_aktivni(rez_dekuji))

        with patch('rezervace.services.emails._odeslat_pro_salon', return_value=True) as smtp:
            self.assertTrue(email_potvrzeni(rez_potvrzeni))
            self.assertTrue(email_storno(rez_potvrzeni, kdo='salon'))
            self.assertGreaterEqual(smtp.call_count, 2)

        with patch('rezervace.services.zivotni_cyklus.email_notifikace') as notif:
            _odeslat_planovane_emaily(now)
            offsets = [call.args[1]['offset'] for call in notif.call_args_list]
            self.assertIn('+24', offsets)
            self.assertNotIn('-2', offsets)

        rez_dekuji.refresh_from_db()
        self.assertIsNotNone(rez_dekuji.thank_you_sent_at)
        self.assertTrue(rez_dekuji.notifikace_odeslane)

    def test_pro_zachova_soucasne_chovani(self):
        salon, partner, _m, _f = self._novy(
            'E5 PRO', 'e5-pro@example.test', plan=PartnerNastaveni.PLAN_PRO,
        )
        self._zapni_tech_flag(salon)
        self._nastaveni(salon)
        now = timezone.now()
        rez_dekuji = self._rezervace(
            salon, stav='dokonceno',
            zacatek=now - timedelta(hours=3),
            konec=now - timedelta(hours=2),
            email='pro-dekuji@e5.test',
        )
        token = self._flow_token('e5-pro@example.test')
        h = self._h(token)
        me = self.client.get('/api/flow/me/', **h).json()
        self.assertEqual(partner.plan, PartnerNastaveni.PLAN_PRO)
        for kod in (
            'imap', 'post_visit_email', 'stats', 'audit',
            'tech_settings', 'noshow_archive',
        ):
            self.assertTrue(me[kod], kod)
        self.assertEqual(self.client.get('/api/flow/mail/stav/', **h).status_code, 200)
        self.assertEqual(self.client.get('/api/flow/owner/statistiky/', **h).status_code, 200)
        self.assertEqual(self.client.get('/api/flow/owner/audit-log/', **h).status_code, 200)
        self.assertEqual(self.client.get('/api/flow/owner/nastaveni/', **h).status_code, 200)
        self.assertEqual(self.client.get('/api/flow/owner/no-show-archiv/', **h).status_code, 200)
        self.assertTrue(partner_ma(salon, FEATURE_IMAP))
        self.assertTrue(dekujici_notifikace_aktivni(rez_dekuji))
        with patch('rezervace.services.zivotni_cyklus.email_notifikace') as notif:
            _odeslat_planovane_emaily(now)
            offsets = [call.args[1]['offset'] for call in notif.call_args_list]
            self.assertIn('-2', offsets)
        log_pred = SalonAuditLog.objects.filter(salon=salon).count()
        rez = self._rezervace(salon, email='pro-noshow@e5.test')
        noshow = self.client.post(
            f'/api/flow/rezervace/{rez.id}/noshow/',
            data={},
            content_type='application/json',
            **h,
        )
        self.assertEqual(noshow.status_code, 200, noshow.content)
        self.assertGreaterEqual(SalonAuditLog.objects.filter(salon=salon).count(), log_pred)

    def test_start_grant_stats_neotevre_ostatni_pro(self):
        salon, partner, _m, _f = self._novy('E5 grant stats', 'e5-grant@example.test')
        self._zapni_tech_flag(salon)
        PartnerFeatureGrant.objects.create(
            salon=salon,
            feature=FEATURE_STATS,
            aktivni=True,
            zdroj=PartnerFeatureGrant.ZDROJ_TEST,
            poznamka='Etapa 5 grant test',
        )
        partner.refresh_from_db()
        self.assertEqual(partner.plan, PartnerNastaveni.PLAN_START)
        self.assertTrue(partner_ma(salon, FEATURE_STATS))
        self.assertFalse(partner_ma(salon, FEATURE_IMAP))
        self.assertFalse(partner_ma(salon, FEATURE_AUDIT))
        self.assertFalse(partner_ma(salon, FEATURE_TECH_SETTINGS))
        self.assertFalse(partner_ma(salon, FEATURE_NOSHOW_ARCHIVE))
        token = self._flow_token('e5-grant@example.test')
        h = self._h(token)
        me = self.client.get('/api/flow/me/', **h).json()
        self.assertTrue(me['stats'])
        self.assertFalse(me['imap'])
        self.assertEqual(self.client.get('/api/flow/owner/statistiky/', **h).status_code, 200)
        self.assertEqual(self.client.get('/api/flow/mail/', **h).status_code, 403)
        self.assertEqual(self.client.get('/api/flow/owner/audit-log/', **h).status_code, 403)
        self.assertEqual(self.client.get('/api/flow/owner/no-show-archiv/', **h).status_code, 403)

    def test_start_web_admin_statistiky_a_audit_403_smtp_ulozene_zustava(self):
        salon, _p, majitel, _f = self._novy('E5 webadmin', 'e5-web@example.test')
        self._nastaveni(salon, smtp_host='smtp.example.test', smtp_user='smtp@e5.test')
        majitel.set_password('DocasneHeslo99')
        majitel.save(update_fields=['password_hash'])
        session = ZamestnanecSession.objects.create(
            zamestnanec=majitel,
            expirace=timezone.now() + timedelta(days=1),
        )
        headers = {'HTTP_X_STAFF_TOKEN': str(session.token)}
        sid = salon.id
        self.assertEqual(
            self.client.get(f'/api/salon/{sid}/rezervace/admin/statistiky/', **headers).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(f'/api/salon/{sid}/rezervace/admin/audit-log/', **headers).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(f'/api/salon/{sid}/rezervace/admin/no-show-archiv/', **headers).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(f'/api/salon/{sid}/admin/email/', **headers).status_code,
            403,
        )
        nast = RezervacniNastaveni.objects.get(salon=salon)
        self.assertEqual(nast.smtp_host, 'smtp.example.test')
        self.assertEqual(nast.smtp_user, 'smtp@e5.test')
        self.assertTrue(nast.imap_enabled)
