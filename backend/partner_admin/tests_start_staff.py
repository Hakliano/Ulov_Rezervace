"""Etapa 2 — personální pravidla START (extra_staff, Manager pracuje)."""
from datetime import datetime, time, timedelta
from pathlib import Path
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from flow.models import FlowSession, FlowUser
from flow.persona_service import set_majitelka_pracuje
from partner_admin.models import PartnerNastaveni
from partner_admin.services import vytvor_noveho_partnera
from partner_admin.staff_limits import (
    MSG_PLAN_START,
    extra_staff_brani_startu,
    aktivni_extra_staff_qs,
    je_pracovni_persona_managera,
    pracovni_persona_managera,
)
from rezervace.models import (
    BlokaceCasu,
    Rezervace,
    RezervacniNastaveni,
    Zamestnanec,
    ZamestnanecAbsence,
    ZamestnanecRozvrh,
    ZamestnanecSluzba,
)
from rezervace.services.availability import generuj_terminy, volni_zamestnanci
from salons.models import CenikPolozka, OteviraciDoba, Salon


@override_settings(MATERIALNIK_STUB=True)
class StartPersonalTests(TestCase):
    def setUp(self):
        cache.clear()
        self.actor = get_user_model().objects.create_superuser(
            username='e2-admin',
            email='e2-admin@example.test',
            password='bezpecne-test-heslo',
        )
        self.client = Client()

    def _novy(self, name, email, *, plan=PartnerNastaveni.PLAN_START, flow=True):
        return vytvor_noveho_partnera(
            data={
                'name': name,
                'majitel_email': email,
                'majitel_heslo': 'DocasneHeslo99',
                'aktivovat_flow': flow,
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

    def _staff_token(self, salon, email, password='DocasneHeslo99'):
        r = self.client.post(
            f'/api/salon/{salon.id}/rezervace/staff/prihlaseni/',
            data={'email': email, 'password': password},
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 200, r.content)
        return r.json()['token']

    def _priprav_sloty(self, salon, persona):
        for den in range(7):
            OteviraciDoba.objects.get_or_create(
                salon=salon, den=den,
                defaults={'od': time(9, 0), 'do': time(17, 0), 'zavreno': False},
            )
        nast, _ = RezervacniNastaveni.objects.get_or_create(salon=salon)
        nast.interval_minut = 30
        nast.min_predstih_hodin = 0
        nast.max_predstih_mesicu = 3
        nast.save()
        sluzba = CenikPolozka.objects.create(
            salon=salon, nazev='Střih', cena=500, delka_minut=30, aktivni=True,
        )
        ZamestnanecSluzba.objects.get_or_create(zamestnanec=persona, sluzba=sluzba)
        datum = timezone.localdate() + timedelta(days=1)
        while datum.weekday() > 4:
            datum += timedelta(days=1)
        return sluzba, datum

    def test_start_ma_pracovni_personu_managera(self):
        salon, partner, majitel, flow_user = self._novy('E2 START', 'e2-start@example.test')
        self.assertEqual(partner.plan, PartnerNastaveni.PLAN_START)
        self.assertIsNotNone(flow_user)
        pz = pracovni_persona_managera(salon)
        self.assertIsNotNone(pz)
        self.assertEqual(pz.role, Zamestnanec.ROLE_ZAMESTNANEC)
        self.assertTrue(pz.aktivni)
        self.assertTrue(je_pracovni_persona_managera(salon, pz))
        self.assertNotEqual(pz.pk, majitel.pk)
        self.assertFalse(aktivni_extra_staff_qs(salon).exists())
        self.assertEqual(
            Zamestnanec.objects.filter(
                salon=salon, role=Zamestnanec.ROLE_ZAMESTNANEC, aktivni=True,
            ).count(),
            1,
        )

    def test_start_sloty_sluzby_smeny_blokace_dovolena_rezervace(self):
        salon, _p, majitel, _f = self._novy('E2 Ops', 'e2-ops@example.test')
        pz = pracovni_persona_managera(salon)
        sluzba, datum = self._priprav_sloty(salon, pz)
        token = self._flow_token('e2-ops@example.test')

        put = self.client.put(
            f'/api/flow/owner/personal/{pz.id}/',
            data={
                'jmeno': 'Marie START',
                'sluzby_ids': [sluzba.id],
                'rozvrh': [
                    {'den': i, 'volno': i >= 5, 'od': '09:00', 'do': '17:00'}
                    if i < 5 else {'den': i, 'volno': True, 'od': None, 'do': None}
                    for i in range(7)
                ],
            },
            content_type='application/json',
            HTTP_X_FLOW_TOKEN=token,
        )
        self.assertEqual(put.status_code, 200, put.content)
        pz.refresh_from_db()
        self.assertEqual(pz.jmeno, 'Marie START')
        self.assertTrue(ZamestnanecSluzba.objects.filter(zamestnanec=pz, sluzba=sluzba).exists())
        self.assertTrue(ZamestnanecRozvrh.objects.filter(zamestnanec=pz, den=0, volno=False).exists())

        start = timezone.make_aware(datetime.combine(datum, time(11, 0)))
        end = start + timedelta(hours=1)
        staff_tok = self._staff_token(salon, 'e2-ops@example.test')
        blok = self.client.post(
            f'/api/salon/{salon.id}/rezervace/admin/blokace/',
            data={'zamestnanec': pz.id, 'zacatek': start.isoformat(), 'konec': end.isoformat(), 'popis': 'soukromě'},
            content_type='application/json',
            HTTP_X_STAFF_TOKEN=staff_tok,
        )
        self.assertEqual(blok.status_code, 201, blok.content)
        self.assertTrue(BlokaceCasu.objects.filter(salon=salon, zamestnanec=pz).exists())

        volno = self.client.post(
            '/api/flow/absence/',
            data={
                'typ': 'dovolena',
                'datum_od': (datum + timedelta(days=7)).isoformat(),
                'datum_do': (datum + timedelta(days=8)).isoformat(),
                'poznamka': 'START volno',
            },
            content_type='application/json',
            HTTP_X_FLOW_TOKEN=token,
        )
        self.assertEqual(volno.status_code, 201, volno.content)
        self.assertEqual(volno.json()['absence']['stav'], 'schvaleno')
        abs_row = ZamestnanecAbsence.objects.get(pk=volno.json()['absence']['id'])
        self.assertEqual(abs_row.zamestnanec_id, pz.id)
        self.assertEqual(abs_row.stav, ZamestnanecAbsence.STAV_SCHVALENO)

        terminy = generuj_terminy(salon, datum, [sluzba.id])
        self.assertTrue(terminy)
        dostupni_ids = {
            z['id']
            for t in terminy
            for z in (t.get('dostupni') or [])
        }
        if not dostupni_ids:
            dostupni_ids = {t['zamestnanec_id'] for t in terminy if t.get('zamestnanec_id')}
        self.assertIn(pz.id, dostupni_ids)
        volni = volni_zamestnanci(
            salon, datum,
            timezone.make_aware(datetime.combine(datum, time(10, 0))),
            timezone.make_aware(datetime.combine(datum, time(10, 30))),
            sluzby_ids=[sluzba.id],
        )
        self.assertEqual([z.id for z in volni], [pz.id])
        self.assertNotIn(majitel.id, [z.id for z in volni])

        rez = Rezervace.objects.create(
            salon=salon,
            zamestnanec=pz,
            zacatek=timezone.make_aware(datetime.combine(datum, time(10, 0))),
            konec=timezone.make_aware(datetime.combine(datum, time(10, 30))),
            stav='potvrzeno',
            jmeno_host='Zákazník START',
        )
        self.assertEqual(rez.zamestnanec_id, pz.id)

        info = self.client.get(f'/api/salon/{salon.id}/rezervace/info/')
        self.assertEqual(info.status_code, 200)
        ids = [z['id'] for z in info.json()['zamestnanci']]
        self.assertEqual(ids, [pz.id])
        self.assertNotIn(majitel.id, ids)

    def test_start_nesmi_pridat_druheho_pracovnika(self):
        salon, _p, _m, _f = self._novy('E2 Lock', 'e2-lock@example.test')
        token = self._flow_token('e2-lock@example.test')
        flow = self.client.post(
            '/api/flow/owner/personal/',
            data={'jmeno': 'Druhá'},
            content_type='application/json',
            HTTP_X_FLOW_TOKEN=token,
        )
        self.assertEqual(flow.status_code, 400, flow.content)

        staff_tok = self._staff_token(salon, 'e2-lock@example.test')
        web = self.client.post(
            f'/api/salon/{salon.id}/rezervace/admin/zamestnanci/',
            data={'jmeno': 'Druhá web'},
            content_type='application/json',
            HTTP_X_STAFF_TOKEN=staff_tok,
        )
        self.assertEqual(web.status_code, 400, web.content)
        self.assertEqual(
            Zamestnanec.objects.filter(salon=salon, role=Zamestnanec.ROLE_ZAMESTNANEC).count(),
            1,
        )

    def test_start_nesmi_vypnout_manager_pracuje(self):
        salon, _p, _m, flow_user = self._novy('E2 Off', 'e2-off@example.test')
        pz_id = pracovni_persona_managera(salon).id
        token = self._flow_token('e2-off@example.test')
        off = self.client.delete('/api/flow/owner/pracovni-persona/', HTTP_X_FLOW_TOKEN=token)
        self.assertEqual(off.status_code, 400, off.content)
        flow_user.refresh_from_db()
        self.assertEqual(flow_user.pracovni_zamestnanec_id, pz_id)

        staff_tok = self._staff_token(salon, 'e2-off@example.test')
        web = self.client.put(
            f'/api/salon/{salon.id}/flow/majitelka-pracuje/',
            data={'ano': False},
            content_type='application/json',
            HTTP_X_STAFF_TOKEN=staff_tok,
        )
        self.assertEqual(web.status_code, 400, web.content)

        deakt = self.client.post(
            f'/api/salon/{salon.id}/rezervace/admin/zamestnanci/{pz_id}/deaktivovat/',
            HTTP_X_STAFF_TOKEN=staff_tok,
        )
        self.assertEqual(deakt.status_code, 400, deakt.content)
        self.assertTrue(Zamestnanec.objects.get(pk=pz_id).aktivni)

    def test_pro_muze_pridat_staff_a_vypnout_manager_pracuje(self):
        salon, partner, _m, flow_user = self._novy(
            'E2 PRO', 'e2-pro@example.test', plan=PartnerNastaveni.PLAN_PRO,
        )
        self.assertEqual(partner.plan, PartnerNastaveni.PLAN_PRO)
        token = self._flow_token('e2-pro@example.test')
        add = self.client.post(
            '/api/flow/owner/personal/',
            data={'jmeno': 'Anna PRO'},
            content_type='application/json',
            HTTP_X_FLOW_TOKEN=token,
        )
        self.assertEqual(add.status_code, 201, add.content)
        off = self.client.delete('/api/flow/owner/pracovni-persona/', HTTP_X_FLOW_TOKEN=token)
        self.assertEqual(off.status_code, 200, off.content)
        flow_user.refresh_from_db()
        self.assertIsNone(flow_user.pracovni_zamestnanec_id)
        on = set_majitelka_pracuje(salon, ano=True, jmeno='Marie PRO')
        self.assertTrue(on['ano'])

    def test_start_na_pro_odemkne_extra_staff_bez_migrace(self):
        salon, partner, _m, _f = self._novy('E2 Up', 'e2-up@example.test')
        pz = pracovni_persona_managera(salon)
        rez = Rezervace.objects.create(
            salon=salon,
            zamestnanec=pz,
            zacatek=timezone.now() + timedelta(days=3),
            konec=timezone.now() + timedelta(days=3, minutes=30),
            stav='potvrzeno',
            jmeno_host='Historie',
        )
        partner.plan = PartnerNastaveni.PLAN_PRO
        partner.save()
        token = self._flow_token('e2-up@example.test')
        add = self.client.post(
            '/api/flow/owner/personal/',
            data={'jmeno': 'Nová po upgradu'},
            content_type='application/json',
            HTTP_X_FLOW_TOKEN=token,
        )
        self.assertEqual(add.status_code, 201, add.content)
        pz.refresh_from_db()
        rez.refresh_from_db()
        self.assertEqual(rez.zamestnanec_id, pz.id)
        self.assertTrue(Zamestnanec.objects.filter(pk=pz.pk, aktivni=True).exists())

    def test_pro_na_start_s_extra_staff_se_odmitne_a_nemaže(self):
        salon, partner, _m, _f = self._novy(
            'E2 Down', 'e2-down@example.test', plan=PartnerNastaveni.PLAN_PRO,
        )
        extra = Zamestnanec.objects.create(
            salon=salon,
            jmeno='Navíc',
            role=Zamestnanec.ROLE_ZAMESTNANEC,
            aktivni=True,
            prihlasovaci_jmeno='navic-e2@example.test',
        )
        rez = Rezervace.objects.create(
            salon=salon,
            zamestnanec=extra,
            zacatek=timezone.now() + timedelta(days=2),
            konec=timezone.now() + timedelta(days=2, minutes=45),
            stav='potvrzeno',
            jmeno_host='U extra',
        )
        partner.plan = PartnerNastaveni.PLAN_START
        with self.assertRaises(ValidationError) as ctx:
            partner.save()
        self.assertIn('plan', ctx.exception.error_dict)
        self.assertIn(MSG_PLAN_START, str(ctx.exception.error_dict['plan']))
        partner.refresh_from_db()
        self.assertEqual(partner.plan, PartnerNastaveni.PLAN_PRO)
        extra.refresh_from_db()
        self.assertTrue(extra.aktivni)
        self.assertTrue(Rezervace.objects.filter(pk=rez.pk, zamestnanec=extra).exists())

    def test_pro_na_start_po_deaktivaci_extra_projde(self):
        salon, partner, _m, _f = self._novy(
            'E2 Hist', 'e2-hist@example.test', plan=PartnerNastaveni.PLAN_PRO,
        )
        extra = Zamestnanec.objects.create(
            salon=salon,
            jmeno='Bývalá',
            role=Zamestnanec.ROLE_ZAMESTNANEC,
            aktivni=False,
            prihlasovaci_jmeno='byvala-e2@example.test',
        )
        partner.plan = PartnerNastaveni.PLAN_START
        partner.save()
        partner.refresh_from_db()
        self.assertEqual(partner.plan, PartnerNastaveni.PLAN_START)
        extra.refresh_from_db()
        self.assertFalse(extra.aktivni)
        self.assertFalse(aktivni_extra_staff_qs(salon).exists())
        self.assertIsNotNone(pracovni_persona_managera(salon))

    def test_me_hlasi_extra_staff_flag(self):
        self._novy('E2 Me S', 'e2-me-s@example.test')
        tok_s = self._flow_token('e2-me-s@example.test')
        me_s = self.client.get('/api/flow/me/', HTTP_X_FLOW_TOKEN=tok_s)
        self.assertEqual(me_s.status_code, 200)
        self.assertFalse(me_s.json()['extra_staff'])
        self.assertTrue(me_s.json()['manager_pracuje_povinny'])
        self.assertEqual(me_s.json()['plan'], 'start')

        self._novy('E2 Me P', 'e2-me-p@example.test', plan=PartnerNastaveni.PLAN_PRO)
        tok_p = self._flow_token('e2-me-p@example.test')
        me_p = self.client.get('/api/flow/me/', HTTP_X_FLOW_TOKEN=tok_p)
        self.assertTrue(me_p.json()['extra_staff'])
        self.assertFalse(me_p.json()['manager_pracuje_povinny'])

    def test_deaktivace_extra_s_budouci_rezervaci_se_odmitne(self):
        salon, _p, _m, _f = self._novy(
            'E2 Fut', 'e2-fut@example.test', plan=PartnerNastaveni.PLAN_PRO,
        )
        extra = Zamestnanec.objects.create(
            salon=salon,
            jmeno='Test PRO',
            role=Zamestnanec.ROLE_ZAMESTNANEC,
            aktivni=True,
            prihlasovaci_jmeno='test-pro-fut@example.test',
        )
        rez = Rezervace.objects.create(
            salon=salon,
            zamestnanec=extra,
            zacatek=timezone.now() + timedelta(days=2),
            konec=timezone.now() + timedelta(days=2, minutes=30),
            stav='potvrzeno',
            jmeno_host='Budoucí',
        )
        staff_tok = self._staff_token(salon, 'e2-fut@example.test')
        r = self.client.post(
            f'/api/salon/{salon.id}/rezervace/admin/zamestnanci/{extra.id}/deaktivovat/',
            HTTP_X_STAFF_TOKEN=staff_tok,
        )
        self.assertEqual(r.status_code, 400, r.content)
        self.assertIn('budoucí rezervace', r.json()['detail'])
        extra.refresh_from_db()
        rez.refresh_from_db()
        self.assertTrue(extra.aktivni)
        self.assertEqual(rez.zamestnanec_id, extra.id)
        self.assertEqual(rez.stav, 'potvrzeno')

    def test_deaktivace_extra_vypne_profil_flow_a_odblokuje_start(self):
        salon, partner, _m, _f = self._novy(
            'E2 Off2', 'e2-off2@example.test', plan=PartnerNastaveni.PLAN_PRO,
        )
        extra = Zamestnanec.objects.create(
            salon=salon,
            jmeno='Test PRO',
            role=Zamestnanec.ROLE_ZAMESTNANEC,
            aktivni=True,
            zobrazit_na_webu=True,
            prihlasovaci_jmeno='test-pro-off@example.test',
        )
        fu = FlowUser.objects.create(
            salon=salon,
            zamestnanec=extra,
            email='test-pro-off-flow@example.test',
            password_hash='x',
            aktivni=True,
        )
        FlowSession.objects.create(
            user=fu,
            expirace=timezone.now() + timedelta(days=1),
        )
        hist = Rezervace.objects.create(
            salon=salon,
            zamestnanec=extra,
            zacatek=timezone.now() - timedelta(days=10),
            konec=timezone.now() - timedelta(days=10, minutes=-30),
            stav='dokonceno',
            jmeno_host='Historie',
        )
        self.assertTrue(extra_staff_brani_startu(salon))
        staff_tok = self._staff_token(salon, 'e2-off2@example.test')
        r = self.client.post(
            f'/api/salon/{salon.id}/rezervace/admin/zamestnanci/{extra.id}/deaktivovat/',
            HTTP_X_STAFF_TOKEN=staff_tok,
        )
        self.assertEqual(r.status_code, 200, r.content)
        extra.refresh_from_db()
        fu.refresh_from_db()
        hist.refresh_from_db()
        self.assertFalse(extra.aktivni)
        self.assertFalse(extra.zobrazit_na_webu)
        self.assertFalse(fu.aktivni)
        self.assertEqual(FlowSession.objects.filter(user=fu).count(), 0)
        self.assertEqual(hist.zamestnanec_id, extra.id)
        self.assertEqual(hist.stav, 'dokonceno')
        self.assertFalse(extra_staff_brani_startu(salon))
        partner.plan = PartnerNastaveni.PLAN_START
        partner.save()
        partner.refresh_from_db()
        self.assertEqual(partner.plan, PartnerNastaveni.PLAN_START)

        act = self.client.post(
            f'/api/salon/{salon.id}/rezervace/admin/zamestnanci/{extra.id}/aktivovat/',
            HTTP_X_STAFF_TOKEN=staff_tok,
        )
        self.assertEqual(act.status_code, 400, act.content)
        extra.refresh_from_db()
        self.assertFalse(extra.aktivni)

    def test_aktivace_extra_na_pro_je_reverzibilni(self):
        salon, _p, _m, _f = self._novy(
            'E2 On', 'e2-on@example.test', plan=PartnerNastaveni.PLAN_PRO,
        )
        extra = Zamestnanec.objects.create(
            salon=salon,
            jmeno='Test PRO',
            role=Zamestnanec.ROLE_ZAMESTNANEC,
            aktivni=True,
            prihlasovaci_jmeno='test-pro-on@example.test',
        )
        staff_tok = self._staff_token(salon, 'e2-on@example.test')
        off = self.client.post(
            f'/api/salon/{salon.id}/rezervace/admin/zamestnanci/{extra.id}/deaktivovat/',
            HTTP_X_STAFF_TOKEN=staff_tok,
        )
        self.assertEqual(off.status_code, 200, off.content)
        on = self.client.post(
            f'/api/salon/{salon.id}/rezervace/admin/zamestnanci/{extra.id}/aktivovat/',
            HTTP_X_STAFF_TOKEN=staff_tok,
        )
        self.assertEqual(on.status_code, 200, on.content)
        extra.refresh_from_db()
        self.assertTrue(extra.aktivni)
        self.assertTrue(extra_staff_brani_startu(salon))

    def test_flow_start_nesmi_aktivovat_extra_ani_obnovit_flow(self):
        salon, partner, _m, _f = self._novy(
            'E2 FlowOff', 'e2-flowoff@example.test', plan=PartnerNastaveni.PLAN_PRO,
        )
        extra = Zamestnanec.objects.create(
            salon=salon,
            jmeno='Test PRO',
            role=Zamestnanec.ROLE_ZAMESTNANEC,
            aktivni=True,
            prihlasovaci_jmeno='test-pro-flowoff@example.test',
        )
        fu = FlowUser.objects.create(
            salon=salon,
            zamestnanec=extra,
            email='test-pro-flowoff@example.test',
            password_hash='x',
            aktivni=False,
        )
        staff_tok = self._staff_token(salon, 'e2-flowoff@example.test')
        self.client.post(
            f'/api/salon/{salon.id}/rezervace/admin/zamestnanci/{extra.id}/deaktivovat/',
            HTTP_X_STAFF_TOKEN=staff_tok,
        )
        extra.refresh_from_db()
        self.assertFalse(extra.aktivni)
        partner.plan = PartnerNastaveni.PLAN_START
        partner.save()
        token = self._flow_token('e2-flowoff@example.test')
        act = self.client.post(
            f'/api/flow/owner/personal/{extra.id}/aktivovat/',
            HTTP_X_FLOW_TOKEN=token,
        )
        self.assertEqual(act.status_code, 400, act.content)
        extra.refresh_from_db()
        self.assertFalse(extra.aktivni)
        flow = self.client.post(
            f'/api/flow/owner/personal/{extra.id}/flow/',
            data={'email': 'test-pro-flowoff2@example.test'},
            content_type='application/json',
            HTTP_X_FLOW_TOKEN=token,
        )
        self.assertEqual(flow.status_code, 400, flow.content)
        patch = self.client.patch(
            f'/api/flow/owner/personal/{extra.id}/flow/patch/',
            data={'aktivni': True},
            content_type='application/json',
            HTTP_X_FLOW_TOKEN=token,
        )
        self.assertEqual(patch.status_code, 400, patch.content)
        fu.refresh_from_db()
        self.assertFalse(fu.aktivni)


FLOW_INDEX = Path(__file__).resolve().parents[2] / 'flow' / 'index.html'
FLOW_JS = Path(__file__).resolve().parents[2] / 'flow' / 'app.js'


@skipUnless(FLOW_INDEX.is_file() and FLOW_JS.is_file(), 'flow/ není v API image')
class FlowStartUxContractTests(TestCase):
    def test_flow_ui_ma_personal_a_blokovany_stav(self):
        html = FLOW_INDEX.read_text(encoding='utf-8')
        js = FLOW_JS.read_text(encoding='utf-8')
        self.assertIn('tab-label">Personál</span>', html)
        self.assertNotIn('tab-label">Staff</span>', html)
        self.assertIn('Přejít na Moderník PRO', html)
        self.assertIn('Moderník START', html)
        self.assertIn('Uživatel byl zablokován.', js)
        self.assertIn('Profil a jeho historie zůstávají zachovány.', js)
        self.assertIn('Váš pracovní profil pro správu provozovny a obsluhu zákazníků.', js)
        self.assertIn('customerVisibleStaff', js)
        self.assertIn('customerOverviewPeople', js)
        self.assertIn('function flowTabAvailable', js)
        self.assertIn('resolvePostLoginTab', js)
        self.assertIn('preserveTab', js)
        self.assertIn('Určuje, zda Manager také přijímá rezervace a obsluhuje zákazníky.', html)
        self.assertIn('Spravujte dovolené a další absence personálu.', html)
        self.assertIn('Heslo můžete změnit v administraci svého webu', html)
        self.assertIn('E-mailová schránka zatím není nastavena.', js)
        self.assertIn('own-volno-zam-wrap', html)
        self.assertNotIn('Historický personál z PRO', js)
        self.assertNotIn('Staff · Manager', js)
        self.assertNotIn('správa + obsluha', js)
        self.assertNotIn('Ne = účet zůstane jen ke správě', html)
        self.assertNotIn('Overview:', html)
        self.assertNotIn('Heslo Manager se mění v administraci webu', html)
        self.assertIn('isStartPlan', js)
        self.assertIn('/flow/owner/personal/${id}/aktivovat/', js)
