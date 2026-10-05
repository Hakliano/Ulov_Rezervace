"""Etapa 3 — Kartotéka / Archivník START vs PRO. Rezervační kontakty se nezamykají."""
from datetime import datetime, time, timedelta
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from archivnik.models import Customer, Entry, Object, ObjectType
from partner_admin.entitlements import (
    FEATURE_ARCHIVNIK,
    FEATURE_EXTRA_STAFF,
    FEATURE_KARTOTEKA,
    FEATURE_MATERIALNIK,
    MSG_KARTOTEKA_NEDOSTUPNA,
    kartoteka_smí_fungovat,
    partner_ma,
)
from partner_admin.models import MODUL_ARCHIVNIK, PartnerFeatureGrant, PartnerModul, PartnerNastaveni
from partner_admin.services import vytvor_noveho_partnera
from partner_admin.services_moduly import archivnik_je_aktivni, nastav_modul
from partner_admin.staff_limits import pracovni_persona_managera
from rezervace.models import Rezervace, RezervacniNastaveni, Zakaznik, Zamestnanec, ZamestnanecSluzba
from salons.models import CenikPolozka, OteviraciDoba

KARTOTEKA_GET = (
    '/api/flow/kartoteka/zakaznici/',
    '/api/flow/kartoteka/zakaznici/lookup/',
    '/api/flow/kartoteka/typy-objektu/',
)

REPO_ROOT = Path(__file__).resolve().parents[2]


class Actor:
    username = 'e3-admin'


@override_settings(MATERIALNIK_STUB=True)
class StartKartotekaTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_superuser(
            username='e3-admin',
            email='e3-admin@example.test',
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

    def _headers(self, token):
        return {'HTTP_X_FLOW_TOKEN': token}

    def _pracovni(self, salon):
        pz = pracovni_persona_managera(salon)
        if pz:
            return pz
        from flow.persona_service import set_majitelka_pracuje
        set_majitelka_pracuje(salon, ano=True, jmeno='Marie PRO')
        return pracovni_persona_managera(salon)

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
            salon=salon, nazev='Střih E3', cena=500, delka_minut=30, aktivni=True,
        )
        ZamestnanecSluzba.objects.get_or_create(zamestnanec=persona, sluzba=sluzba)
        datum = timezone.localdate() + timedelta(days=1)
        while datum.weekday() > 4:
            datum += timedelta(days=1)
        return sluzba, datum

    def _zaloz_kartoteku(self, salon, *, email='kart@e3.test'):
        typ = ObjectType.objects.create(salon=salon, nazev='Pes')
        cust = Customer.objects.create(
            salon=salon,
            jmeno='Lucie',
            prijmeni='Kartová',
            email=email,
            telefon='777111222',
        )
        obj = Object.objects.create(salon=salon, zakaznik=cust, typ=typ, nazev='Max')
        zapis = Entry.objects.create(
            salon=salon,
            zakaznik=cust,
            objekt=obj,
            text='Historický zápis E3',
            typ_zapisu='Poznámka',
            nadpis='Start',
            nastalo=timezone.now(),
        )
        return cust, obj, zapis

    def _assert_kartoteka_zamcena(self, token, customer_uuid=None):
        h = self._headers(token)
        for path in KARTOTEKA_GET:
            r = self.client.get(path, **h)
            self.assertEqual(r.status_code, 403, path)
            self.assertEqual(r.json()['detail'], MSG_KARTOTEKA_NEDOSTUPNA)
        r = self.client.post(
            '/api/flow/kartoteka/zakaznici/',
            data={'email': 'novy@e3.test', 'kontaktni_jmeno': 'Nový'},
            content_type='application/json',
            **h,
        )
        self.assertEqual(r.status_code, 403)
        if customer_uuid:
            r = self.client.get(f'/api/flow/kartoteka/zakaznici/{customer_uuid}/', **h)
            self.assertEqual(r.status_code, 403)
            r = self.client.post(
                f'/api/flow/kartoteka/zakaznici/{customer_uuid}/zapisy/',
                data={'text': 'x'},
                content_type='application/json',
                **h,
            )
            self.assertEqual(r.status_code, 403)
            r = self.client.post(
                f'/api/flow/kartoteka/zakaznici/{customer_uuid}/objekty/',
                data={'nazev': 'x'},
                content_type='application/json',
                **h,
            )
            self.assertEqual(r.status_code, 403)

    def test_start_rezervace_kontakty_kalendar_noshow_zakaznik_api(self):
        salon, partner, _m, _f = self._novy('E3 START ops', 'e3-ops@example.test')
        pz = self._pracovni(salon)
        sluzba, datum = self._priprav_sloty(salon, pz)
        token = self._flow_token('e3-ops@example.test')
        h = self._headers(token)

        me = self.client.get('/api/flow/me/', **h)
        self.assertEqual(me.status_code, 200)
        self.assertFalse(me.json()['kartoteka'])
        self.assertFalse(me.json()['archivnik_active'])
        self.assertNotIn('archivnik', me.json().get('moduly') or {})
        self.assertFalse(kartoteka_smí_fungovat(salon))

        created = self.client.post(
            '/api/flow/rezervace/',
            data={
                'zamestnanec_id': pz.id,
                'sluzby': [sluzba.id],
                'datum': datum.isoformat(),
                'cas': '10:00',
                'nick': 'Anna START',
                'email': 'anna.start@example.test',
                'poznamka_zakaznika': 'Tel. 777000111 · blond',
            },
            content_type='application/json',
            **h,
        )
        self.assertEqual(created.status_code, 201, created.content)
        body = created.json()
        self.assertEqual(body['kontaktni_jmeno'], 'Anna START')
        self.assertEqual(body['kontaktni_email'], 'anna.start@example.test')
        self.assertIn('blond', body.get('poznamka_zakaznika') or '')
        rez_id = body['id']

        kal = self.client.get('/api/flow/kalendar/', **h)
        self.assertEqual(kal.status_code, 200)
        rows = kal.json()['rezervace']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['kontaktni_jmeno'], 'Anna START')
        self.assertEqual(rows[0]['kontaktni_email'], 'anna.start@example.test')
        self.assertIsNone(rows[0]['archivnik_customer_uuid'])

        preview = self.client.post(
            f'/api/flow/rezervace/{rez_id}/email-preview/',
            data={'typ': 'storno'},
            content_type='application/json',
            **h,
        )
        self.assertEqual(preview.status_code, 200, preview.content)
        self.assertNotEqual(preview.status_code, 403)

        noshow = self.client.post(
            f'/api/flow/rezervace/{rez_id}/noshow/',
            data={},
            content_type='application/json',
            **h,
        )
        self.assertEqual(noshow.status_code, 200, noshow.content)
        rez = Rezervace.objects.get(pk=rez_id)
        self.assertEqual(rez.stav, 'no_show')

        reg = self.client.post(
            f'/api/salon/{salon.id}/rezervace/zakaznik/registrace/',
            data={
                'nick': 'Petr Účet',
                'email': 'petr.ucet@example.test',
                'password': 'HesloZakaznik9',
                'ochrana_udaju_souhlas': True,
            },
            content_type='application/json',
        )
        self.assertIn(reg.status_code, (200, 201), reg.content)
        ztoken = reg.json()['token']
        Rezervace.objects.create(
            salon=salon,
            zamestnanec=pz,
            zakaznik=Zakaznik.objects.get(salon=salon, email='petr.ucet@example.test'),
            zacatek=timezone.make_aware(datetime.combine(datum, time(11, 0))),
            konec=timezone.make_aware(datetime.combine(datum, time(11, 30))),
            stav='potvrzeno',
        )
        moje = self.client.get(
            f'/api/salon/{salon.id}/rezervace/zakaznik/moje/',
            data={'token': ztoken},
        )
        self.assertEqual(moje.status_code, 200, moje.content)
        self.assertEqual(moje.json()['zakaznik']['email'], 'petr.ucet@example.test')
        self.assertTrue(moje.json()['budouci'])

        self._assert_kartoteka_zamcena(token)

        arch = self.client.post(
            '/api/archivnik/auth/login/',
            data={'email': 'e3-ops@example.test', 'password': 'DocasneHeslo99'},
            content_type='application/json',
        )
        self.assertEqual(arch.status_code, 403)

        self.client.force_login(self.actor)
        zap = self.client.post(
            reverse('partner_admin:nastavit_archivnik', args=[salon.id]),
            {'zapnout': '1'},
        )
        self.assertEqual(zap.status_code, 302)
        self.assertFalse(archivnik_je_aktivni(salon))
        self.assertFalse(partner_ma(salon, FEATURE_ARCHIVNIK))

    def test_start_nesmi_kartoteku_ani_s_natvrdo_zapnutym_modulem(self):
        salon, _p, _m, _f = self._novy('E3 leftover', 'e3-left@example.test')
        nastav_modul(salon, MODUL_ARCHIVNIK, False, Actor())
        PartnerModul.objects.filter(salon=salon, modul__kod=MODUL_ARCHIVNIK).update(
            status=PartnerModul.STAV_ACTIVE,
        )
        salon.refresh_from_db()
        self.assertTrue(archivnik_je_aktivni(salon))
        self.assertFalse(kartoteka_smí_fungovat(salon))
        token = self._flow_token('e3-left@example.test')
        self._assert_kartoteka_zamcena(token)
        me = self.client.get('/api/flow/me/', **self._headers(token))
        self.assertFalse(me.json()['kartoteka'])
        self.assertNotIn('archivnik', me.json().get('moduly') or {})

    def test_pro_archivnik_on_kartoteka_funguje(self):
        salon, _p, _m, _f = self._novy(
            'E3 PRO on', 'e3-pro-on@example.test', plan=PartnerNastaveni.PLAN_PRO,
        )
        self.assertTrue(kartoteka_smí_fungovat(salon))
        cust, obj, zapis = self._zaloz_kartoteku(salon, email='lucie@e3-pro.test')
        token = self._flow_token('e3-pro-on@example.test')
        h = self._headers(token)
        me = self.client.get('/api/flow/me/', **h)
        self.assertTrue(me.json()['kartoteka'])
        self.assertTrue(me.json()['archivnik_active'])

        lst = self.client.get('/api/flow/kartoteka/zakaznici/', **h)
        self.assertEqual(lst.status_code, 200)
        uuidy = {row['uuid'] for row in lst.json()['vysledky']}
        self.assertIn(str(cust.uuid), uuidy)

        detail = self.client.get(f'/api/flow/kartoteka/zakaznici/{cust.uuid}/', **h)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()['email'], 'lucie@e3-pro.test')
        self.assertTrue(detail.json()['objekty'])
        self.assertTrue(detail.json()['posledni_zapisy'])

        typy = self.client.get('/api/flow/kartoteka/typy-objektu/', **h)
        self.assertEqual(typy.status_code, 200)
        self.assertTrue(typy.json())

        arch = self.client.post(
            '/api/archivnik/auth/login/',
            data={'email': 'e3-pro-on@example.test', 'password': 'DocasneHeslo99'},
            content_type='application/json',
        )
        self.assertEqual(arch.status_code, 200, arch.content)
        customers = self.client.get(
            '/api/archivnik/customers/',
            HTTP_X_ARCHIVNIK_TOKEN=arch.json()['token'],
        )
        self.assertEqual(customers.status_code, 200)
        self.assertTrue(obj.pk)
        self.assertTrue(zapis.pk)

    def test_pro_archivnik_off_kartoteka_pryc_ostatni_pro_zustava(self):
        salon, partner, _m, _f = self._novy(
            'E3 PRO off', 'e3-pro-off@example.test', plan=PartnerNastaveni.PLAN_PRO,
        )
        cust, _o, _z = self._zaloz_kartoteku(salon, email='off@e3.test')
        nastav_modul(salon, MODUL_ARCHIVNIK, False, Actor())
        partner.refresh_from_db()
        self.assertEqual(partner.plan, PartnerNastaveni.PLAN_PRO)
        self.assertTrue(partner_ma(salon, FEATURE_KARTOTEKA))
        self.assertTrue(partner_ma(salon, FEATURE_EXTRA_STAFF))
        self.assertTrue(partner_ma(salon, FEATURE_MATERIALNIK))
        self.assertFalse(kartoteka_smí_fungovat(salon))
        self.assertTrue(Customer.objects.filter(pk=cust.pk).exists())

        token = self._flow_token('e3-pro-off@example.test')
        me = self.client.get('/api/flow/me/', **self._headers(token))
        self.assertFalse(me.json()['kartoteka'])
        self.assertTrue(me.json()['extra_staff'])
        self._assert_kartoteka_zamcena(token, cust.uuid)

        add = self.client.post(
            '/api/flow/owner/personal/',
            data={'jmeno': 'Další PRO'},
            content_type='application/json',
            **self._headers(token),
        )
        self.assertEqual(add.status_code, 201, add.content)

        arch = self.client.post(
            '/api/archivnik/auth/login/',
            data={'email': 'e3-pro-off@example.test', 'password': 'DocasneHeslo99'},
            content_type='application/json',
        )
        self.assertEqual(arch.status_code, 403)

        pz = self._pracovni(salon)
        rez = Rezervace.objects.create(
            salon=salon,
            zamestnanec=pz,
            zacatek=timezone.now() + timedelta(days=2),
            konec=timezone.now() + timedelta(days=2, minutes=30),
            stav='potvrzeno',
            jmeno_host='Kontakt OFF',
            email_host='off.kontakt@e3.test',
        )
        kal = self.client.get('/api/flow/kalendar/', **self._headers(token))
        row = next(r for r in kal.json()['rezervace'] if r['id'] == rez.id)
        self.assertEqual(row['kontaktni_jmeno'], 'Kontakt OFF')
        self.assertEqual(row['kontaktni_email'], 'off.kontakt@e3.test')
        self.assertIsNone(row['archivnik_customer_uuid'])

    def test_archivnik_off_on_data_zustanou(self):
        salon, _p, _m, _f = self._novy(
            'E3 restore', 'e3-rest@example.test', plan=PartnerNastaveni.PLAN_PRO,
        )
        cust, obj, zapis = self._zaloz_kartoteku(salon, email='restore@e3.test')
        nastav_modul(salon, MODUL_ARCHIVNIK, False, Actor())
        self.assertFalse(kartoteka_smí_fungovat(salon))
        self.assertTrue(Customer.objects.filter(pk=cust.pk).exists())
        self.assertTrue(Object.objects.filter(pk=obj.pk).exists())
        self.assertTrue(Entry.objects.filter(pk=zapis.pk).exists())

        nastav_modul(salon, MODUL_ARCHIVNIK, True, Actor())
        self.assertTrue(kartoteka_smí_fungovat(salon))
        token = self._flow_token('e3-rest@example.test')
        detail = self.client.get(
            f'/api/flow/kartoteka/zakaznici/{cust.uuid}/',
            **self._headers(token),
        )
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()['email'], 'restore@e3.test')
        self.assertEqual(detail.json()['objekty'][0]['nazev'], 'Max')
        texts = {e['text'] for e in detail.json()['posledni_zapisy']}
        self.assertIn('Historický zápis E3', texts)

    def test_start_na_pro_bez_migrace_po_aktivaci_kartoteka(self):
        salon, partner, _m, _f = self._novy('E3 up', 'e3-up@example.test')
        pz = pracovni_persona_managera(salon)
        rez = Rezervace.objects.create(
            salon=salon,
            zamestnanec=pz,
            zacatek=timezone.now() + timedelta(days=4),
            konec=timezone.now() + timedelta(days=4, minutes=30),
            stav='potvrzeno',
            jmeno_host='Historie START',
            email_host='hist.start@e3.test',
        )
        partner.plan = PartnerNastaveni.PLAN_PRO
        partner.save()
        rez.refresh_from_db()
        self.assertEqual(rez.jmeno_host, 'Historie START')
        self.assertEqual(rez.zamestnanec_id, pz.id)
        nastav_modul(salon, MODUL_ARCHIVNIK, True, Actor())
        self.assertTrue(kartoteka_smí_fungovat(salon))
        token = self._flow_token('e3-up@example.test')
        lst = self.client.get('/api/flow/kartoteka/zakaznici/', **self._headers(token))
        self.assertEqual(lst.status_code, 200)
        kal = self.client.get('/api/flow/kalendar/', **self._headers(token))
        row = next(r for r in kal.json()['rezervace'] if r['id'] == rez.id)
        self.assertEqual(row['kontaktni_jmeno'], 'Historie START')
        self.assertEqual(row['kontaktni_email'], 'hist.start@e3.test')

    def test_pro_na_start_znepristupni_archivnik_nemaže_data(self):
        salon, partner, _m, _f = self._novy(
            'E3 down', 'e3-down@example.test', plan=PartnerNastaveni.PLAN_PRO,
        )
        cust, obj, zapis = self._zaloz_kartoteku(salon, email='down@e3.test')
        self.assertTrue(kartoteka_smí_fungovat(salon))
        partner.plan = PartnerNastaveni.PLAN_START
        partner.save()
        partner.refresh_from_db()
        self.assertEqual(partner.plan, PartnerNastaveni.PLAN_START)
        self.assertFalse(archivnik_je_aktivni(salon))
        self.assertFalse(kartoteka_smí_fungovat(salon))
        self.assertTrue(Customer.objects.filter(pk=cust.pk).exists())
        self.assertTrue(Object.objects.filter(pk=obj.pk).exists())
        self.assertTrue(Entry.objects.filter(pk=zapis.pk).exists())
        token = self._flow_token('e3-down@example.test')
        self._assert_kartoteka_zamcena(token, cust.uuid)

        partner.plan = PartnerNastaveni.PLAN_PRO
        partner.save()
        nastav_modul(salon, MODUL_ARCHIVNIK, True, Actor())
        detail = self.client.get(
            f'/api/flow/kartoteka/zakaznici/{cust.uuid}/',
            **self._headers(self._flow_token('e3-down@example.test')),
        )
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()['email'], 'down@e3.test')

    def test_grant_kartoteka_bez_archivniku_nema_druhou_kartoteku(self):
        salon, _p, _m, _f = self._novy('E3 grant', 'e3-grant@example.test')
        PartnerFeatureGrant.objects.create(
            salon=salon,
            feature=FEATURE_KARTOTEKA,
            zakaz=False,
            zdroj=PartnerFeatureGrant.ZDROJ_TRIAL,
        )
        self.assertTrue(partner_ma(salon, FEATURE_KARTOTEKA))
        self.assertFalse(kartoteka_smí_fungovat(salon))
        token = self._flow_token('e3-grant@example.test')
        self._assert_kartoteka_zamcena(token)

    def test_flow_ui_skryva_kartoteku_podle_flagu(self):
        app = (REPO_ROOT / 'flow' / 'app.js').read_text(encoding='utf-8')
        cc = (REPO_ROOT / 'flow' / 'customer-card.js').read_text(encoding='utf-8')
        html = (REPO_ROOT / 'flow' / 'index.html').read_text(encoding='utf-8')
        self.assertIn('function kartotekaSmiFungovat', app)
        self.assertIn('function applyKartotekaUi', app)
        self.assertIn("name === 'karty' && !kartotekaSmiFungovat()", app)
        self.assertIn("id=\"tab-karty\"", html)
        self.assertIn('kartotekaSmiFungovat', cc)
        self.assertIn('Otevřít kartu zákazníka', cc)
        self.assertIn('Založit zákazníka', cc)
