"""P5.1 — FLOW read proxy nad Archivníkem: tenant isolation, matching, kalendář."""
from __future__ import annotations

import inspect
import uuid
from datetime import date, timedelta

from django.test import Client, TestCase
from django.utils import timezone

import archivnik.models as archivnik_models
import archivnik.views as archivnik_views
from archivnik.models import Customer, Entry, Object, ObjectType, Reminder, ReminderStav, Stav
from flow.models import FlowSession, FlowUser
from rezervace.models import Rezervace, Zakaznik, Zamestnanec
from salons.models import Salon


def _flow_ucet(salon, email, password, *, jmeno='Majitel', role=None):
    role = role or Zamestnanec.ROLE_MAJITEL
    zam = Zamestnanec.objects.create(
        salon=salon,
        jmeno=jmeno,
        role=role,
        prihlasovaci_jmeno=email,
        aktivni=True,
        zobrazit_na_webu=False,
    )
    zam.set_password(password)
    zam.save(update_fields=['password_hash'])
    flow = FlowUser.objects.create(
        salon=salon,
        zamestnanec=zam,
        email=email,
        aktivni=True,
        visible_overview=True,
    )
    flow.password_hash = zam.password_hash
    flow.save(update_fields=['password_hash'])
    return zam, flow


class KartotekaFlowProxyTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.salon_a = Salon.objects.create(name='Salon A', email='a@test.local')
        self.salon_b = Salon.objects.create(name='Salon B', email='b@test.local')
        self.owner_a, self.flow_a = _flow_ucet(self.salon_a, 'owner-a@test.local', 'HesloA123', jmeno='Owner A')
        self.owner_b, self.flow_b = _flow_ucet(self.salon_b, 'owner-b@test.local', 'HesloB123', jmeno='Owner B')

        self.typ_a = ObjectType.objects.create(salon=self.salon_a, nazev='Pes')
        self.typ_kocka = ObjectType.objects.create(salon=self.salon_a, nazev='Kočka')
        self.typ_b = ObjectType.objects.create(salon=self.salon_b, nazev='Pes')

        self.jan = Customer.objects.create(
            salon=self.salon_a,
            jmeno='Jan',
            prijmeni='Novák',
            email='jan@novak.cz',
            telefon='777123456',
            poznamka='Alergie na barvu.',
        )
        self.max = Object.objects.create(
            salon=self.salon_a, zakaznik=self.jan, typ=self.typ_a, nazev='Max',
        )
        self.micka = Object.objects.create(
            salon=self.salon_a, zakaznik=self.jan, typ=self.typ_kocka, nazev='Micka',
        )
        self.zapis_stary = Entry.objects.create(
            salon=self.salon_a,
            zakaznik=self.jan,
            objekt=self.max,
            nastalo=timezone.now() - timedelta(days=10),
            typ_zapisu='Kontrola',
            nadpis='Starší',
            text='Starší zápis',
        )
        self.zapis_novy = Entry.objects.create(
            salon=self.salon_a,
            zakaznik=self.jan,
            objekt=None,
            nastalo=timezone.now() - timedelta(hours=2),
            typ_zapisu='Kontrola',
            nadpis='Kontrola',
            text='Bez komplikací',
        )
        Reminder.objects.create(
            salon=self.salon_a,
            zakaznik=self.jan,
            objekt=self.max,
            termin=date.today() - timedelta(days=3),
            text='Očkování prošlo',
            stav=ReminderStav.AKTIVNI,
        )
        Reminder.objects.create(
            salon=self.salon_a,
            zakaznik=self.jan,
            termin=date.today() + timedelta(days=14),
            text='Kontrola za 14 dní',
            stav=ReminderStav.AKTIVNI,
        )
        Reminder.objects.create(
            salon=self.salon_a,
            zakaznik=self.jan,
            termin=date.today(),
            text='Hotovo — nemá se ukázat',
            stav=ReminderStav.HOTOVO,
        )

        self.bez_mailu = Customer.objects.create(
            salon=self.salon_a,
            jmeno='Eva',
            prijmeni='Bezmailová',
            email='',
            telefon='777000111',
        )
        self.bez_objektu = Customer.objects.create(
            salon=self.salon_a,
            jmeno='Petr',
            prijmeni='Sám',
            email='petr.sam@test.local',
        )

        self.boris = Customer.objects.create(
            salon=self.salon_b,
            jmeno='Boris',
            prijmeni='Novák',
            email='jan@novak.cz',
            telefon='999888777',
        )
        self.objekt_b = Object.objects.create(
            salon=self.salon_b, zakaznik=self.boris, typ=self.typ_b, nazev='Rex',
        )
        self.zapis_b = Entry.objects.create(
            salon=self.salon_b,
            zakaznik=self.boris,
            objekt=self.objekt_b,
            text='Cizí zápis tenanta B',
        )
        self.reminder_b = Reminder.objects.create(
            salon=self.salon_b,
            zakaznik=self.boris,
            termin=date.today() + timedelta(days=1),
            text='Cizí připomínka',
            stav=ReminderStav.AKTIVNI,
        )

    def _login(self, email, password):
        r = self.client.post(
            '/api/flow/prihlaseni/',
            data={'email': email, 'password': password},
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 200)
        return r.json()['token']

    def _get(self, path, token, **params):
        return self.client.get(path, data=params or None, HTTP_X_FLOW_TOKEN=token)

    def test_bez_tokenu_403(self):
        r = self.client.get('/api/flow/kartoteka/zakaznici/')
        self.assertEqual(r.status_code, 403)

    def test_list_jen_vlastni_tenant(self):
        token = self._login('owner-a@test.local', 'HesloA123')
        r = self._get('/api/flow/kartoteka/zakaznici/', token)
        self.assertEqual(r.status_code, 200)
        body = r.json()
        uuidy = {row['uuid'] for row in body['vysledky']}
        self.assertIn(str(self.jan.uuid), uuidy)
        self.assertIn(str(self.bez_mailu.uuid), uuidy)
        self.assertIn(str(self.bez_objektu.uuid), uuidy)
        self.assertNotIn(str(self.boris.uuid), uuidy)
        self.assertEqual(body['celkem'], 3)
        self.assertIn('stranka', body)
        self.assertIn('page_size', body)

    def test_list_paginace(self):
        token = self._login('owner-a@test.local', 'HesloA123')
        r = self._get('/api/flow/kartoteka/zakaznici/', token, page=1, page_size=1)
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(len(body['vysledky']), 1)
        self.assertEqual(body['celkem'], 3)
        self.assertEqual(body['celkem_stranek'], 3)
        self.assertEqual(body['page_size'], 1)
        page2 = self._get('/api/flow/kartoteka/zakaznici/', token, page=2, page_size=1).json()
        self.assertEqual(len(page2['vysledky']), 1)
        self.assertNotEqual(body['vysledky'][0]['uuid'], page2['vysledky'][0]['uuid'])

    def test_list_search(self):
        token = self._login('owner-a@test.local', 'HesloA123')
        r = self._get('/api/flow/kartoteka/zakaznici/', token, q='novák')
        uuidy = {row['uuid'] for row in r.json()['vysledky']}
        self.assertEqual(uuidy, {str(self.jan.uuid)})
        tel = self._get('/api/flow/kartoteka/zakaznici/', token, q='777000111')
        self.assertEqual({row['uuid'] for row in tel.json()['vysledky']}, {str(self.bez_mailu.uuid)})

    def test_list_ignoruje_podstrcene_salon_id(self):
        token = self._login('owner-a@test.local', 'HesloA123')
        r = self._get('/api/flow/kartoteka/zakaznici/', token, salon_id=self.salon_b.id)
        uuidy = {row['uuid'] for row in r.json()['vysledky']}
        self.assertNotIn(str(self.boris.uuid), uuidy)
        self.assertIn(str(self.jan.uuid), uuidy)

    def test_detail_kontakt_objekty_zapisy_pripominky(self):
        token = self._login('owner-a@test.local', 'HesloA123')
        r = self._get(f'/api/flow/kartoteka/zakaznici/{self.jan.uuid}/', token)
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body['jmeno'], 'Jan')
        self.assertEqual(body['prijmeni'], 'Novák')
        self.assertEqual(body['email'], 'jan@novak.cz')
        self.assertEqual(body['telefon'], '777123456')
        self.assertEqual(body['poznamka'], 'Alergie na barvu.')
        objekty = {(o['nazev'], o['typ_nazev']) for o in body['objekty']}
        self.assertEqual(objekty, {('Max', 'Pes'), ('Micka', 'Kočka')})
        self.assertGreaterEqual(len(body['posledni_zapisy']), 2)
        self.assertEqual(body['posledni_zapisy'][0]['text'], 'Bez komplikací')
        self.assertIsNone(body['posledni_zapisy'][0]['objekt_uuid'])
        texts = {p['text'] for p in body['pripominky']}
        self.assertIn('Očkování prošlo', texts)
        self.assertIn('Kontrola za 14 dní', texts)
        self.assertNotIn('Hotovo — nemá se ukázat', texts)
        self.assertTrue(body['ma_proslou_pripominku'])
        self.assertTrue(body['ma_aktivni_pripominku'])
        self.assertIn('zakaznik=', body['archivnik_url'])
        self.assertNotIn(str(self.objekt_b.uuid), {o['uuid'] for o in body['objekty']})
        self.assertNotIn(str(self.zapis_b.uuid), {e['uuid'] for e in body['posledni_zapisy']})
        self.assertNotIn(str(self.reminder_b.uuid), {p['uuid'] for p in body['pripominky']})

    def test_detail_zakaznik_bez_objektu(self):
        token = self._login('owner-a@test.local', 'HesloA123')
        r = self._get(f'/api/flow/kartoteka/zakaznici/{self.bez_objektu.uuid}/', token)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['objekty'], [])
        self.assertEqual(r.json()['posledni_zapisy'], [])
        self.assertFalse(r.json()['ma_aktivni_pripominku'])

    def test_detail_zakaznik_bez_emailu(self):
        token = self._login('owner-a@test.local', 'HesloA123')
        r = self._get(f'/api/flow/kartoteka/zakaznici/{self.bez_mailu.uuid}/', token)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['email'], '')
        self.assertEqual(r.json()['prijmeni'], 'Bezmailová')

    def test_cizi_customer_uuid_404(self):
        token = self._login('owner-a@test.local', 'HesloA123')
        r = self._get(f'/api/flow/kartoteka/zakaznici/{self.boris.uuid}/', token)
        self.assertEqual(r.status_code, 404)

    def test_nahodne_uuid_404(self):
        token = self._login('owner-a@test.local', 'HesloA123')
        r = self._get(f'/api/flow/kartoteka/zakaznici/{uuid.uuid4()}/', token)
        self.assertEqual(r.status_code, 404)

    def test_cizi_object_entry_reminder_nejsou_v_detailu_a_nemaji_standalone_route(self):
        token = self._login('owner-a@test.local', 'HesloA123')
        for path in (
            f'/api/flow/kartoteka/objekty/{self.objekt_b.uuid}/',
            f'/api/flow/kartoteka/zapisy/{self.zapis_b.uuid}/',
            f'/api/flow/kartoteka/pripominky/{self.reminder_b.uuid}/',
            f'/api/flow/kartoteka/objekty/{self.max.uuid}/',
        ):
            r = self._get(path, token)
            self.assertEqual(r.status_code, 404, path)

    def test_lookup_presna_shoda_a_normalizace(self):
        token = self._login('owner-a@test.local', 'HesloA123')
        exact = self._get('/api/flow/kartoteka/zakaznici/lookup/', token, email='jan@novak.cz')
        self.assertEqual(exact.json()['uuid'], str(self.jan.uuid))
        case = self._get('/api/flow/kartoteka/zakaznici/lookup/', token, email='JAN@NOVAK.CZ')
        self.assertEqual(case.json()['uuid'], str(self.jan.uuid))
        space = self._get('/api/flow/kartoteka/zakaznici/lookup/', token, email='  jan@novak.cz  ')
        self.assertEqual(space.json()['uuid'], str(self.jan.uuid))

    def test_lookup_no_match_a_chybejici_email(self):
        token = self._login('owner-a@test.local', 'HesloA123')
        none = self._get('/api/flow/kartoteka/zakaznici/lookup/', token, email='neexistuje@test.local')
        self.assertEqual(none.json(), {'uuid': None})
        empty = self._get('/api/flow/kartoteka/zakaznici/lookup/', token)
        self.assertEqual(empty.json(), {'uuid': None})
        blank = self._get('/api/flow/kartoteka/zakaznici/lookup/', token, email='   ')
        self.assertEqual(blank.json(), {'uuid': None})

    def test_lookup_neslucuje_podle_jmena_ani_telefonu(self):
        token = self._login('owner-a@test.local', 'HesloA123')
        r = self._get(
            '/api/flow/kartoteka/zakaznici/lookup/',
            token,
            email='jiny@test.local',
            jmeno='Jan Novák',
            telefon='777123456',
        )
        self.assertEqual(r.json(), {'uuid': None})

    def test_lookup_nema_cizi_tenant_stejny_email(self):
        token = self._login('owner-a@test.local', 'HesloA123')
        r = self._get('/api/flow/kartoteka/zakaznici/lookup/', token, email='jan@novak.cz')
        self.assertEqual(r.json()['uuid'], str(self.jan.uuid))
        token_b = self._login('owner-b@test.local', 'HesloB123')
        r_b = self._get('/api/flow/kartoteka/zakaznici/lookup/', token_b, email='jan@novak.cz')
        self.assertEqual(r_b.json()['uuid'], str(self.boris.uuid))

    def test_lookup_zakaznik_bez_emailu_se_nema_matchovat(self):
        token = self._login('owner-a@test.local', 'HesloA123')
        r = self._get('/api/flow/kartoteka/zakaznici/lookup/', token, email='eva.bezmailova@test.local')
        self.assertEqual(r.json(), {'uuid': None})

    def _kalendar(self, token):
        return self._get('/api/flow/kalendar/', token)

    def test_kalendar_registrovany_match(self):
        zak = Zakaznik.objects.create(
            salon=self.salon_a, nick='Jan', email='jan@novak.cz',
        )
        now = timezone.now()
        Rezervace.objects.create(
            salon=self.salon_a,
            zamestnanec=self.owner_a,
            zakaznik=zak,
            zacatek=now,
            konec=now + timedelta(hours=1),
            stav='potvrzeno',
        )
        token = self._login('owner-a@test.local', 'HesloA123')
        rows = self._kalendar(token).json()['rezervace']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['archivnik_customer_uuid'], str(self.jan.uuid))
        self.assertEqual(rows[0]['kontaktni_email'], 'jan@novak.cz')

    def test_kalendar_host_s_emailem_match(self):
        now = timezone.now()
        Rezervace.objects.create(
            salon=self.salon_a,
            zamestnanec=self.owner_a,
            zacatek=now,
            konec=now + timedelta(hours=1),
            stav='potvrzeno',
            jmeno_host='Jan Host',
            email_host='JAN@novak.cz',
        )
        token = self._login('owner-a@test.local', 'HesloA123')
        row = self._kalendar(token).json()['rezervace'][0]
        self.assertEqual(row['archivnik_customer_uuid'], str(self.jan.uuid))

    def test_kalendar_host_bez_emailu(self):
        now = timezone.now()
        Rezervace.objects.create(
            salon=self.salon_a,
            zamestnanec=self.owner_a,
            zacatek=now,
            konec=now + timedelta(hours=1),
            stav='potvrzeno',
            jmeno_host='Host bez mailu',
            email_host='',
        )
        token = self._login('owner-a@test.local', 'HesloA123')
        row = self._kalendar(token).json()['rezervace'][0]
        self.assertIsNone(row['archivnik_customer_uuid'])

    def test_kalendar_zadny_odpovidajici_customer(self):
        now = timezone.now()
        Rezervace.objects.create(
            salon=self.salon_a,
            zamestnanec=self.owner_a,
            zacatek=now,
            konec=now + timedelta(hours=1),
            stav='potvrzeno',
            jmeno_host='Cizí',
            email_host='nikdo@test.local',
        )
        token = self._login('owner-a@test.local', 'HesloA123')
        row = self._kalendar(token).json()['rezervace'][0]
        self.assertIsNone(row['archivnik_customer_uuid'])

    def test_kalendar_nema_cizi_tenant_customer(self):
        now = timezone.now()
        Rezervace.objects.create(
            salon=self.salon_a,
            zamestnanec=self.owner_a,
            zacatek=now,
            konec=now + timedelta(hours=1),
            stav='potvrzeno',
            jmeno_host='Boris mail v A neexistuje jako B',
            email_host='jiny-nez-boris@test.local',
        )
        Customer.objects.create(
            salon=self.salon_b, prijmeni='Jiný', email='jiny-nez-boris@test.local',
        )
        token = self._login('owner-a@test.local', 'HesloA123')
        row = self._kalendar(token).json()['rezervace'][0]
        self.assertIsNone(row['archivnik_customer_uuid'])

    def test_flow_token_neotevre_archivnik_api(self):
        token = self._login('owner-a@test.local', 'HesloA123')
        r = self.client.get(
            f'/api/archivnik/customers/{self.jan.uuid}/',
            HTTP_X_FLOW_TOKEN=token,
        )
        self.assertIn(r.status_code, (401, 403))

    def test_archivnik_token_neotevre_flow_kartoteku(self):
        r = self.client.get(
            '/api/flow/kartoteka/zakaznici/',
            HTTP_X_ARCHIVNIK_TOKEN='not-a-flow-token',
        )
        self.assertEqual(r.status_code, 403)

    def test_write_zatim_neni(self):
        token = self._login('owner-a@test.local', 'HesloA123')
        post = self.client.post(
            '/api/flow/kartoteka/zakaznici/',
            data={'prijmeni': 'Nový'},
            content_type='application/json',
            HTTP_X_FLOW_TOKEN=token,
        )
        self.assertEqual(post.status_code, 405)

    def test_list_nevraci_cely_nekapacitni_dump_bez_limitu(self):
        token = self._login('owner-a@test.local', 'HesloA123')
        r = self._get('/api/flow/kartoteka/zakaznici/', token, page_size=9999)
        self.assertLessEqual(r.json()['page_size'], 100)


class KartotekaStandaloneArchivnikTests(TestCase):
    def test_archivnik_modely_neimportuji_flow(self):
        src_models = inspect.getsource(archivnik_models)
        src_views = inspect.getsource(archivnik_views)
        for src in (src_models, src_views):
            self.assertNotIn('CustomerCard', src)
            self.assertNotIn('CustomerVisit', src)
            self.assertNotIn('kartoteka_services', src)
            self.assertNotIn('kartoteka_views', src)
        self.assertNotIn('from flow', src_models)
        self.assertNotIn('import flow', src_models)

    def test_archivnik_funguje_bez_flow_uctu(self):
        salon = Salon.objects.create(name='Sólo Archivník', email='solo-p51@archivnik.test')
        owner = Zamestnanec.objects.create(
            salon=salon,
            jmeno='Majitel sólo',
            role=Zamestnanec.ROLE_MAJITEL,
            prihlasovaci_jmeno='solo-p51@archivnik.test',
            aktivni=True,
            zobrazit_na_webu=False,
        )
        owner.set_password('archivnik123')
        owner.save(update_fields=['password_hash'])
        from partner_admin.models import MODUL_ARCHIVNIK, ModulKatalog, PartnerModul
        katalog, _ = ModulKatalog.objects.get_or_create(
            kod=MODUL_ARCHIVNIK,
            defaults={'nazev': 'Archivník', 'popis': '', 'razeni': 20},
        )
        PartnerModul.objects.update_or_create(
            salon=salon, modul=katalog, defaults={'status': PartnerModul.STAV_ACTIVE},
        )
        self.assertFalse(FlowUser.objects.filter(salon=salon).exists())
        client = Client()
        login = client.post(
            '/api/archivnik/auth/login/',
            data={'email': 'solo-p51@archivnik.test', 'password': 'archivnik123'},
            content_type='application/json',
        )
        self.assertEqual(login.status_code, 200)
        token = login.json()['token']
        Customer.objects.create(salon=salon, prijmeni='Walkin', jmeno='Anna', email='')
        seznam = client.get('/api/archivnik/customers/', HTTP_X_ARCHIVNIK_TOKEN=token)
        self.assertEqual(seznam.status_code, 200)
        self.assertEqual(len(seznam.json()), 1)
        self.assertEqual(seznam.json()[0]['prijmeni'], 'Walkin')
        self.assertFalse(FlowUser.objects.filter(salon=salon).exists())
        self.assertEqual(FlowSession.objects.filter(user__salon=salon).count(), 0)
        self.assertEqual(Customer.objects.filter(salon=salon).first().stav, Stav.AKTIVNI)
