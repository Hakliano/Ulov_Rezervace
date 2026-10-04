"""Etapa 6 — integrační ověření START/PRO přes reálné založení partnera."""
from datetime import datetime, time, timedelta
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from flow.persona_service import set_majitelka_pracuje
from partner_admin.entitlements import (
    FEATURE_AUDIT,
    FEATURE_EXTRA_STAFF,
    FEATURE_IMAP,
    FEATURE_KARTOTEKA,
    FEATURE_MATERIALNIK,
    FEATURE_NOSHOW_ARCHIVE,
    FEATURE_POST_VISIT_EMAIL,
    FEATURE_STATS,
    FEATURE_TECH_SETTINGS,
    FEATURES,
    MSG_FUNKCE_NEDOSTUPNA,
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
from partner_admin.services_moduly import (
    archivnik_je_aktivni,
    nastav_modul,
    odeber_materialnik_grant,
    partner_modul,
    povol_materialnik_individulne,
)
from partner_admin.staff_limits import (
    aktivni_extra_staff_qs,
    pracovni_persona_managera,
)
from rezervace.models import (
    Rezervace,
    RezervacniNastaveni,
    Zamestnanec,
    ZamestnanecAbsence,
    ZamestnanecRozvrh,
    ZamestnanecSluzba,
)
from rezervace.notifikace_defaults import vychozi_notifikace
from rezervace.services.emails import email_potvrzeni, email_storno
from rezervace.services.gdpr import dekujici_notifikace_aktivni
from rezervace.services.zivotni_cyklus import _odeslat_planovane_emaily
from salons.models import CenikPolozka, OteviraciDoba

REPO_ROOT = Path(__file__).resolve().parents[2]
PRO_FLAGS = (
    'imap', 'post_visit_email', 'stats', 'audit',
    'tech_settings', 'noshow_archive',
)


class Actor:
    username = 'e6-admin'


@override_settings(MATERIALNIK_STUB=True, MATERIALNIK_M2M_KEY='test-m2m')
class Etapa6StartProIntegrationTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_superuser(
            username='e6-admin',
            email='e6-admin@example.test',
            password='bezpecne-test-heslo',
        )
        self.client = Client()
        self.client.force_login(self.actor)

    def _zalozeni_pres_admin(self, name, email, *, plan, testovaci=True):
        res = self.client.post(
            reverse('partner_admin:novy'),
            {
                'name': name,
                'majitel_email': email,
                'majitel_heslo': 'DocasneHeslo99',
                'aktivovat_flow': 'on',
                'plan': plan,
                'tarif': 'Moderník',
                'castka': '1590.00',
                'je_testovaci': 'on' if testovaci else '',
                'periodicita': PartnerNastaveni.PERIODA_MESIC,
            },
        )
        self.assertEqual(res.status_code, 302, res.content)
        from salons.models import Salon
        salon = Salon.objects.get(name=name)
        return salon, salon.partner_nastaveni

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

    def _staff_token(self, salon, email, password='DocasneHeslo99'):
        r = self.client.post(
            f'/api/salon/{salon.id}/rezervace/staff/prihlaseni/',
            data={'email': email, 'password': password},
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()['token']

    def _priprav_provoz(self, salon):
        pz = pracovni_persona_managera(salon)
        self.assertIsNotNone(pz)
        for den in range(7):
            OteviraciDoba.objects.get_or_create(
                salon=salon, den=den,
                defaults={'od': time(9, 0), 'do': time(17, 0), 'zavreno': False},
            )
        nast, _ = RezervacniNastaveni.objects.get_or_create(salon=salon)
        nast.interval_minut = 30
        nast.min_predstih_hodin = 0
        nast.max_predstih_mesicu = 3
        nast.notifikace = vychozi_notifikace()
        nast.save()
        sluzba = CenikPolozka.objects.create(
            salon=salon, nazev='Střih START', cena=450, delka_minut=30, aktivni=True,
        )
        ZamestnanecSluzba.objects.get_or_create(zamestnanec=pz, sluzba=sluzba)
        for i in range(5):
            ZamestnanecRozvrh.objects.update_or_create(
                zamestnanec=pz, den=i,
                defaults={'volno': False, 'od': time(9, 0), 'do': time(17, 0)},
            )
        datum = timezone.localdate() + timedelta(days=1)
        while datum.weekday() > 4:
            datum += timedelta(days=1)
        return pz, sluzba, datum

    def test_zalozeni_start_pres_partner_admin_a_kompletni_pruchod(self):
        salon, partner = self._zalozeni_pres_admin(
            'START Demo referenční', 'start.demo@ulovklienty.test',
            plan=PartnerNastaveni.PLAN_START,
        )
        self.assertEqual(partner.plan, PartnerNastaveni.PLAN_START)
        self.assertEqual(partner.tarif, 'Moderník')
        self.assertTrue(partner.je_testovaci)
        majitel = Zamestnanec.objects.get(salon=salon, role=Zamestnanec.ROLE_MAJITEL)
        self.assertTrue(hasattr(majitel, 'flow_ucet'))
        pz = pracovni_persona_managera(salon)
        self.assertIsNotNone(pz)
        self.assertTrue(pz.aktivni)
        self.assertFalse(aktivni_extra_staff_qs(salon).exists())
        self.assertFalse(archivnik_je_aktivni(salon))
        self.assertFalse(materialnik_smí_fungovat(salon))
        self.assertFalse(kartoteka_smí_fungovat(salon))
        for feature in FEATURES:
            self.assertFalse(partner_ma(salon, feature), feature)

        detail = self.client.get(
            reverse('partner_admin:detail', args=[salon.id]) + '?tab=partner',
        )
        self.assertContains(detail, 'Plán')
        self.assertContains(detail, 'START')
        self.assertContains(detail, 'Tarif')
        self.assertContains(detail, 'Moderník')
        self.assertContains(detail, 'Není součástí plánu START')
        self.assertContains(detail, 'Povolit Materiálník')
        self.assertNotContains(detail, 'Zapnout Archivník')
        self.assertContains(detail, 'Testovací partner')
        self.assertContains(detail, 'name="je_testovaci"')

        pz, sluzba, datum = self._priprav_provoz(salon)
        token = self._flow_token('start.demo@ulovklienty.test')
        h = self._h(token)
        me = self.client.get('/api/flow/me/', **h).json()
        self.assertEqual(me['plan'], 'start')
        self.assertTrue(me['manager_pracuje_povinny'])
        self.assertFalse(me['extra_staff'])
        self.assertFalse(me['kartoteka'])
        for kod in PRO_FLAGS:
            self.assertFalse(me[kod], kod)
        self.assertNotIn('materialnik', me.get('moduly') or {})

        self.assertEqual(self.client.get('/api/flow/kalendar/', **h).status_code, 200)
        self.assertEqual(self.client.get('/api/flow/owner/personal/', **h).status_code, 200)
        self.assertEqual(self.client.get('/api/flow/sluzby/', **h).status_code, 200)
        self.assertEqual(self.client.get('/api/flow/owner/personal/', **h).status_code, 200)
        pro_locked = [
            '/api/flow/mail/',
            '/api/flow/mail/stav/',
            '/api/flow/owner/statistiky/',
            '/api/flow/owner/audit-log/',
            '/api/flow/owner/nastaveni/',
            '/api/flow/owner/no-show-archiv/',
        ]
        for path in pro_locked:
            r = self.client.get(path, **h)
            self.assertEqual(r.status_code, 403, path)
            self.assertEqual(r.json()['detail'], MSG_FUNKCE_NEDOSTUPNA)
        kart = self.client.get('/api/flow/kartoteka/zakaznici/', **h)
        self.assertEqual(kart.status_code, 403)
        mat = self.client.get('/api/flow/materialnik-prehled/', **h)
        self.assertIn(mat.status_code, (403, 404))

        extra = self.client.post(
            '/api/flow/owner/personal/',
            data={'jmeno': 'Druhá START'},
            content_type='application/json',
            **h,
        )
        self.assertEqual(extra.status_code, 400)
        persona_off = self.client.delete('/api/flow/owner/pracovni-persona/', **h)
        self.assertEqual(persona_off.status_code, 400)
        staff_tok = self._staff_token(salon, 'start.demo@ulovklienty.test')
        web_extra = self.client.post(
            f'/api/salon/{salon.id}/rezervace/admin/zamestnanci/',
            data={'jmeno': 'Druhá web'},
            content_type='application/json',
            HTTP_X_STAFF_TOKEN=staff_tok,
        )
        self.assertEqual(web_extra.status_code, 400)

        info = self.client.get(f'/api/salon/{salon.id}/rezervace/info/')
        self.assertEqual(info.status_code, 200)
        ids = [z['id'] for z in info.json()['zamestnanci']]
        self.assertEqual(ids, [pz.id])
        self.assertNotIn(majitel.id, ids)

        terminy = self.client.get(
            f'/api/salon/{salon.id}/rezervace/volne-terminy/',
            {'datum': datum.isoformat(), 'sluzby': str(sluzba.id)},
        )
        self.assertEqual(terminy.status_code, 200, terminy.content)
        self.assertTrue(terminy.json()['terminy'])

        created = self.client.post(
            f'/api/salon/{salon.id}/rezervace/',
            data={
                'sluzby': [sluzba.id],
                'datum': datum.isoformat(),
                'cas': '10:00',
                'zamestnanec_id': pz.id,
                'nick': 'Jana Demo',
                'email': 'jana.demo@example.test',
                'poznamka': 'Tel. 777111222',
                'ochrana_udaju_souhlas': True,
            },
            content_type='application/json',
        )
        self.assertEqual(created.status_code, 201, created.content)
        rez_id = created.json()['id']
        rez = Rezervace.objects.get(pk=rez_id)
        self.assertEqual(rez.zamestnanec_id, pz.id)
        self.assertEqual(rez.kontaktni_jmeno, 'Jana Demo')
        self.assertEqual(rez.kontaktni_email, 'jana.demo@example.test')
        kal = self.client.get('/api/flow/kalendar/', **h)
        row = next(r for r in kal.json()['rezervace'] if r['id'] == rez_id)
        self.assertEqual(row['kontaktni_email'], 'jana.demo@example.test')
        self.assertIsNone(row.get('archivnik_customer_uuid'))

        put_persona = self.client.put(
            f'/api/flow/owner/personal/{pz.id}/',
            data={
                'jmeno': 'Manager START',
                'sluzby_ids': [sluzba.id],
            },
            content_type='application/json',
            **h,
        )
        self.assertEqual(put_persona.status_code, 200, put_persona.content)
        volno = self.client.post(
            '/api/flow/absence/',
            data={
                'typ': 'dovolena',
                'datum_od': (datum + timedelta(days=14)).isoformat(),
                'datum_do': (datum + timedelta(days=15)).isoformat(),
                'poznamka': 'START volno',
            },
            content_type='application/json',
            **h,
        )
        self.assertEqual(volno.status_code, 201, volno.content)
        self.assertEqual(volno.json()['absence']['stav'], 'schvaleno')
        self.assertEqual(
            ZamestnanecAbsence.objects.get(pk=volno.json()['absence']['id']).zamestnanec_id,
            pz.id,
        )

        flow_rez = self.client.post(
            '/api/flow/rezervace/',
            data={
                'sluzby': [sluzba.id],
                'datum': datum.isoformat(),
                'cas': '11:00',
                'zamestnanec_id': pz.id,
                'nick': 'Telefonický',
                'email': 'telefon@e6.test',
                'poznamka_interni': 'přesun analog',
            },
            content_type='application/json',
            **h,
        )
        self.assertEqual(flow_rez.status_code, 201, flow_rez.content)
        prevest = self.client.post(
            f'/api/flow/rezervace/{flow_rez.json()["id"]}/prevest/',
            data={'zamestnanec_id': majitel.id},
            content_type='application/json',
            **h,
        )
        self.assertIn(prevest.status_code, (400, 403), prevest.content)

        rez.stav = 'potvrzeno'
        rez.save(update_fields=['stav'])
        with patch('rezervace.services.emails._odeslat_pro_salon', return_value=True) as smtp:
            self.assertTrue(email_potvrzeni(rez))
            self.assertTrue(email_storno(rez, kdo='salon'))
            self.assertGreaterEqual(smtp.call_count, 2)

        now = timezone.now()
        rez_prip = Rezervace.objects.create(
            salon=salon, zamestnanec=pz,
            zacatek=now + timedelta(hours=24),
            konec=now + timedelta(hours=24, minutes=30),
            stav='potvrzeno', jmeno_host='Připomínka', email_host='prip@e6.test',
        )
        rez_po = Rezervace.objects.create(
            salon=salon, zamestnanec=pz,
            zacatek=now - timedelta(hours=3),
            konec=now - timedelta(hours=2),
            stav='dokonceno', jmeno_host='Po návštěvě', email_host='po@e6.test',
        )
        self.assertFalse(dekujici_notifikace_aktivni(rez_po))
        with patch('rezervace.services.zivotni_cyklus.email_notifikace') as notif:
            _odeslat_planovane_emaily(now)
            offsets = [c.args[1]['offset'] for c in notif.call_args_list]
            self.assertIn('+24', offsets)
            self.assertNotIn('-2', offsets)
        rez_po.refresh_from_db()
        self.assertIsNotNone(rez_po.thank_you_sent_at)

        storno = self.client.delete(
            f'/api/flow/rezervace/{rez_prip.id}/storno/',
            **h,
        )
        self.assertEqual(storno.status_code, 200, storno.content)
        dokoncena = Rezervace.objects.create(
            salon=salon, zamestnanec=pz,
            zacatek=now - timedelta(minutes=40),
            konec=now - timedelta(minutes=10),
            stav='potvrzeno', jmeno_host='Hotovo', email_host='hotovo@e6.test',
        )
        done = self.client.post(
            f'/api/flow/rezervace/{dokoncena.id}/dokonceno/',
            data={}, content_type='application/json', **h,
        )
        self.assertEqual(done.status_code, 200, done.content)
        noshow_rez = Rezervace.objects.create(
            salon=salon, zamestnanec=pz,
            zacatek=now + timedelta(days=2),
            konec=now + timedelta(days=2, minutes=30),
            stav='potvrzeno', jmeno_host='NoShow', email_host='ns@e6.test',
        )
        noshow = self.client.post(
            f'/api/flow/rezervace/{noshow_rez.id}/noshow/',
            data={}, content_type='application/json', **h,
        )
        self.assertEqual(noshow.status_code, 200, noshow.content)
        noshow_rez.refresh_from_db()
        self.assertEqual(noshow_rez.stav, 'no_show')
        self.assertEqual(
            self.client.get('/api/flow/owner/no-show-archiv/', **h).status_code, 403,
        )

        arch = self.client.post(
            '/api/archivnik/auth/login/',
            data={'email': 'start.demo@ulovklienty.test', 'password': 'DocasneHeslo99'},
            content_type='application/json',
        )
        self.assertEqual(arch.status_code, 403)

        self.assertFalse(materialnik_smí_fungovat(salon))
        self.client.post(
            reverse('partner_admin:nastavit_materialnik', args=[salon.id]),
            {'akce': 'povolit'},
        )
        partner.refresh_from_db()
        self.assertEqual(partner.plan, PartnerNastaveni.PLAN_START)
        self.assertTrue(partner_ma(salon, FEATURE_MATERIALNIK))
        self.assertTrue(materialnik_smí_fungovat(salon))
        self.assertFalse(partner_ma(salon, FEATURE_IMAP))
        me2 = self.client.get('/api/flow/me/', **h).json()
        self.assertIn('materialnik', me2.get('moduly') or {})
        self.assertFalse(me2['stats'])
        sess = self.client.post(
            '/api/integrations/v1/materialnik/session',
            data={'email': 'start.demo@ulovklienty.test', 'password': 'DocasneHeslo99'},
            content_type='application/json',
            HTTP_X_ULOV_M2M_KEY='test-m2m',
        )
        self.assertEqual(sess.status_code, 200, sess.content)
        modul_row = partner_modul(salon, MODUL_MATERIALNIK)
        self.assertEqual(modul_row.status, PartnerModul.STAV_ACTIVE)

        self.client.post(
            reverse('partner_admin:nastavit_materialnik', args=[salon.id]),
            {'akce': 'vypnout'},
        )
        self.assertTrue(partner_ma(salon, FEATURE_MATERIALNIK))
        self.assertFalse(materialnik_smí_fungovat(salon))
        self.assertTrue(PartnerModul.objects.filter(salon=salon, modul__kod=MODUL_MATERIALNIK).exists())

        self.client.post(
            reverse('partner_admin:nastavit_materialnik', args=[salon.id]),
            {'akce': 'zapnout'},
        )
        self.assertTrue(materialnik_smí_fungovat(salon))

        self.client.post(
            reverse('partner_admin:nastavit_materialnik', args=[salon.id]),
            {'akce': 'odebrat'},
        )
        self.assertFalse(partner_ma(salon, FEATURE_MATERIALNIK))
        self.assertFalse(materialnik_smí_fungovat(salon))
        self.assertTrue(PartnerModul.objects.filter(salon=salon, modul__kod=MODUL_MATERIALNIK).exists())
        sess2 = self.client.post(
            '/api/integrations/v1/materialnik/session',
            data={'email': 'start.demo@ulovklienty.test', 'password': 'DocasneHeslo99'},
            content_type='application/json',
            HTTP_X_ULOV_M2M_KEY='test-m2m',
        )
        self.assertEqual(sess2.status_code, 401)

        ted = timezone.now()
        povol_materialnik_individulne(salon, Actor(), platnost_do=ted + timedelta(days=7))
        self.assertTrue(materialnik_smí_fungovat(salon))
        grant = PartnerFeatureGrant.objects.filter(
            salon=salon, feature=FEATURE_MATERIALNIK, aktivni=True, zakaz=False,
        ).latest('vytvoreno')
        grant.platnost_do = ted - timedelta(hours=1)
        grant.save(update_fields=['platnost_do'])
        self.assertFalse(partner_ma(salon, FEATURE_MATERIALNIK))
        me3 = self.client.get('/api/flow/me/', **h).json()
        self.assertNotIn('materialnik', me3.get('moduly') or {})
        self.assertTrue(PartnerModul.objects.filter(salon=salon, modul__kod=MODUL_MATERIALNIK).exists())
        povol_materialnik_individulne(salon, Actor())
        self.assertTrue(materialnik_smí_fungovat(salon))
        odeber_materialnik_grant(salon, Actor())

        PartnerFeatureGrant.objects.create(
            salon=salon, feature=FEATURE_STATS, aktivni=True,
            zdroj=PartnerFeatureGrant.ZDROJ_TEST,
        )
        self.assertEqual(partner.plan, PartnerNastaveni.PLAN_START)
        self.assertTrue(partner_ma(salon, FEATURE_STATS))
        self.assertFalse(partner_ma(salon, FEATURE_IMAP))
        self.assertEqual(self.client.get('/api/flow/owner/statistiky/', **h).status_code, 200)
        self.assertEqual(self.client.get('/api/flow/mail/', **h).status_code, 403)
        PartnerFeatureGrant.objects.filter(salon=salon, feature=FEATURE_STATS).update(aktivni=False)
        self.assertFalse(partner_ma(salon, FEATURE_STATS))
        self.assertEqual(self.client.get('/api/flow/owner/statistiky/', **h).status_code, 403)
        self.assertTrue(Rezervace.objects.filter(pk=rez_id).exists())

        rez_id_pred = rez_id
        tenant = partner.tenant_uuid
        partner.plan = PartnerNastaveni.PLAN_PRO
        partner.save()
        partner.refresh_from_db()
        self.assertEqual(partner.plan, PartnerNastaveni.PLAN_PRO)
        self.assertEqual(partner.tenant_uuid, tenant)
        self.assertTrue(pracovni_persona_managera(salon).aktivni)
        self.assertTrue(Rezervace.objects.filter(pk=rez_id_pred).exists())
        for feature in FEATURES:
            self.assertTrue(partner_ma(salon, feature), feature)
        self.assertTrue(archivnik_je_aktivni(salon))
        self.assertTrue(kartoteka_smí_fungovat(salon))
        self.assertTrue(materialnik_smí_fungovat(salon))
        PartnerNastaveni.objects.filter(pk=partner.pk).update(povolit_technicke_nastaveni=True)
        me_pro = self.client.get('/api/flow/me/', **h).json()
        for kod in PRO_FLAGS:
            self.assertTrue(me_pro[kod], kod)
        self.assertEqual(self.client.get('/api/flow/mail/stav/', **h).status_code, 200)
        self.assertEqual(self.client.get('/api/flow/owner/statistiky/', **h).status_code, 200)
        self.assertEqual(self.client.get('/api/flow/owner/audit-log/', **h).status_code, 200)
        self.assertEqual(self.client.get('/api/flow/owner/nastaveni/', **h).status_code, 200)
        self.assertEqual(self.client.get('/api/flow/owner/no-show-archiv/', **h).status_code, 200)
        self.assertTrue(archivnik_je_aktivni(salon) or partner_ma(salon, FEATURE_KARTOTEKA))

        extra_ok = self.client.post(
            '/api/flow/owner/personal/',
            data={'jmeno': 'Druhá PRO'},
            content_type='application/json',
            **h,
        )
        self.assertEqual(extra_ok.status_code, 201, extra_ok.content)
        extra_id = extra_ok.json()['id']
        with self.assertRaises(ValidationError) as ctx:
            partner.plan = PartnerNastaveni.PLAN_START
            partner.save()
        self.assertIn('plan', ctx.exception.error_dict)
        partner.refresh_from_db()
        self.assertEqual(partner.plan, PartnerNastaveni.PLAN_PRO)
        self.assertTrue(Zamestnanec.objects.filter(pk=extra_id, aktivni=True).exists())

        Zamestnanec.objects.filter(pk=extra_id).update(aktivni=False)
        partner.plan = PartnerNastaveni.PLAN_START
        partner.save()
        partner.refresh_from_db()
        self.assertEqual(partner.plan, PartnerNastaveni.PLAN_START)
        self.assertTrue(pracovni_persona_managera(salon).aktivni)
        self.assertFalse(archivnik_je_aktivni(salon))
        self.assertFalse(kartoteka_smí_fungovat(salon))
        self.assertFalse(materialnik_smí_fungovat(salon))
        for kod in (
            FEATURE_IMAP, FEATURE_STATS, FEATURE_AUDIT, FEATURE_TECH_SETTINGS,
            FEATURE_NOSHOW_ARCHIVE, FEATURE_POST_VISIT_EMAIL, FEATURE_EXTRA_STAFF,
        ):
            self.assertFalse(partner_ma(salon, kod), kod)
        self.assertTrue(Rezervace.objects.filter(pk=rez_id_pred).exists())
        self.assertTrue(Zamestnanec.objects.filter(pk=extra_id).exists())

    def test_existujici_pro_demo_analog_zachova_chovani(self):
        salon, partner = self._zalozeni_pres_admin(
            'PRO Demo regrese', 'pro.demo@ulovklienty.test',
            plan=PartnerNastaveni.PLAN_PRO,
        )
        PartnerNastaveni.objects.filter(pk=partner.pk).update(povolit_technicke_nastaveni=True)
        self.assertEqual(partner.plan, PartnerNastaveni.PLAN_PRO)
        for feature in FEATURES:
            self.assertTrue(partner_ma(salon, feature), feature)
        token = self._flow_token('pro.demo@ulovklienty.test')
        h = self._h(token)
        me = self.client.get('/api/flow/me/', **h).json()
        for kod in PRO_FLAGS:
            self.assertTrue(me[kod], kod)
        self.assertTrue(me['extra_staff'])
        self.assertEqual(self.client.get('/api/flow/owner/statistiky/', **h).status_code, 200)
        self.assertEqual(self.client.get('/api/flow/owner/no-show-archiv/', **h).status_code, 200)
        self.assertEqual(self.client.get('/api/flow/mail/stav/', **h).status_code, 200)
        self.assertEqual(self.client.get('/api/flow/kalendar/', **h).status_code, 200)

    def test_flow_ui_start_neotevira_prehled(self):
        app = (REPO_ROOT / 'flow' / 'app.js').read_text(encoding='utf-8')
        self.assertIn("maProFeature('stats', user) ? 'overview' : 'mujden'", app)
        self.assertIn('function applyStartStaffUi', app)
        self.assertIn('function applyProFeaturesUi', app)
        self.assertIn("user?.extra_staff === false", app)
        html = (REPO_ROOT / 'flow' / 'index.html').read_text(encoding='utf-8')
        self.assertIn('id="tab-karty"', html)
        self.assertIn('class="tab hidden" data-tab="karty"', html)
        self.assertIn('id="tab-mail"', html)
        self.assertIn('data-tab="overview"', html)
        cc = (REPO_ROOT / 'flow' / 'customer-card.js').read_text(encoding='utf-8')
        self.assertIn('kartotekaSmiFungovat', cc)
        self.assertIn('Otevřít kartu zákazníka', cc)
