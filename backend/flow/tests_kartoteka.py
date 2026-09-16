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

    def test_create_bez_emailu_400(self):
        token = self._login('owner-a@test.local', 'HesloA123')
        post = self.client.post(
            '/api/flow/kartoteka/zakaznici/',
            data={'prijmeni': 'Nový'},
            content_type='application/json',
            HTTP_X_FLOW_TOKEN=token,
        )
        self.assertEqual(post.status_code, 400)
        self.assertIn('e-mail', post.json()['detail'].lower())

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


class KartotekaWriteTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.salon_a = Salon.objects.create(name='Write A', email='wa@test.local')
        self.salon_b = Salon.objects.create(name='Write B', email='wb@test.local')
        self.owner_a, self.flow_a = _flow_ucet(
            self.salon_a, 'write-a@test.local', 'HesloA123', jmeno='Owner A',
        )
        self.staff_a, self.flow_staff = _flow_ucet(
            self.salon_a, 'staff-a@test.local', 'StaffA123',
            jmeno='Staff A', role=Zamestnanec.ROLE_ZAMESTNANEC,
        )
        self.owner_b, self.flow_b = _flow_ucet(
            self.salon_b, 'write-b@test.local', 'HesloB123', jmeno='Owner B',
        )
        self.typ_a = ObjectType.objects.create(
            salon=self.salon_a, nazev='Pes', vyzaduje_nazev=True,
        )
        self.typ_bez_nazvu = ObjectType.objects.create(
            salon=self.salon_a, nazev='Chrup', vyzaduje_nazev=False,
        )
        self.typ_b = ObjectType.objects.create(
            salon=self.salon_b, nazev='Pes', vyzaduje_nazev=True,
        )
        self.eva = Customer.objects.create(
            salon=self.salon_a, jmeno='Eva', prijmeni='Nová', email='eva@write.test',
        )
        self.max = Object.objects.create(
            salon=self.salon_a, zakaznik=self.eva, typ=self.typ_a, nazev='Max',
        )
        self.archiv = Customer.objects.create(
            salon=self.salon_a, jmeno='Arch', prijmeni='Ivovaný',
            email='archiv@write.test', stav=Stav.ARCHIVOVANY,
        )
        self.boris = Customer.objects.create(
            salon=self.salon_b, jmeno='Boris', prijmeni='Cizí', email='boris@write.test',
        )
        self.rex = Object.objects.create(
            salon=self.salon_b, zakaznik=self.boris, typ=self.typ_b, nazev='Rex',
        )

    def _login(self, email, password):
        r = self.client.post(
            '/api/flow/prihlaseni/',
            data={'email': email, 'password': password},
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 200)
        return r.json()['token']

    def _post(self, path, token, data):
        return self.client.post(
            path, data=data, content_type='application/json', HTTP_X_FLOW_TOKEN=token,
        )

    def test_create_z_rezervace_jmeno_telefon_autor(self):
        now = timezone.now()
        rez = Rezervace.objects.create(
            salon=self.salon_a,
            zamestnanec=self.owner_a,
            zacatek=now,
            konec=now + timedelta(hours=1),
            stav='potvrzeno',
            jmeno_host='Jan Pavel Novák',
            email_host='JAN.Pavel@Novak.CZ',
        )
        token = self._login('write-a@test.local', 'HesloA123')
        r = self._post(
            '/api/flow/kartoteka/zakaznici/',
            token,
            {'rezervace_id': rez.id, 'telefon': '777123456', 'salon_id': self.salon_b.id},
        )
        self.assertEqual(r.status_code, 201)
        body = r.json()
        self.assertTrue(body['vytvoreno'])
        z = body['zakaznik']
        self.assertEqual(z['jmeno'], 'Jan Pavel')
        self.assertEqual(z['prijmeni'], 'Novák')
        self.assertEqual(z['email'], 'jan.pavel@novak.cz')
        self.assertEqual(z['telefon'], '777123456')
        self.assertEqual(z['stav'], 'aktivni')
        cust = Customer.objects.get(uuid=z['uuid'])
        self.assertEqual(cust.salon_id, self.salon_a.id)
        self.assertEqual(cust.vytvoril_id, self.owner_a.id)
        from flow.customer_card_models import CustomerCard, CustomerVisit
        self.assertEqual(CustomerCard.objects.filter(salon=self.salon_a).count(), 0)
        self.assertEqual(CustomerVisit.objects.count(), 0)

    def test_create_jedno_slovo_prijmeni(self):
        token = self._login('write-a@test.local', 'HesloA123')
        r = self._post(
            '/api/flow/kartoteka/zakaznici/',
            token,
            {'email': 'jednoslov@test.local', 'kontaktni_jmeno': 'Novák'},
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()['zakaznik']['jmeno'], '')
        self.assertEqual(r.json()['zakaznik']['prijmeni'], 'Novák')

    def test_create_chybejici_email_400(self):
        now = timezone.now()
        rez = Rezervace.objects.create(
            salon=self.salon_a,
            zamestnanec=self.owner_a,
            zacatek=now,
            konec=now + timedelta(hours=1),
            stav='potvrzeno',
            jmeno_host='Host',
            email_host='',
        )
        token = self._login('write-a@test.local', 'HesloA123')
        r = self._post('/api/flow/kartoteka/zakaznici/', token, {'rezervace_id': rez.id})
        self.assertEqual(r.status_code, 400)
        blank = self._post(
            '/api/flow/kartoteka/zakaznici/', token, {'kontaktni_jmeno': 'Jan Novák'},
        )
        self.assertEqual(blank.status_code, 400)

    def test_create_existujici_email_bez_duplicity(self):
        token = self._login('write-a@test.local', 'HesloA123')
        r = self._post(
            '/api/flow/kartoteka/zakaznici/',
            token,
            {'email': 'eva@write.test', 'kontaktni_jmeno': 'Někdo Jiný', 'telefon': '111'},
        )
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json()['vytvoreno'])
        self.assertEqual(r.json()['zakaznik']['uuid'], str(self.eva.uuid))
        self.assertEqual(r.json()['zakaznik']['prijmeni'], 'Nová')
        self.assertEqual(Customer.objects.filter(salon=self.salon_a, email__iexact='eva@write.test').count(), 1)

    def test_create_case_whitespace_duplicate(self):
        token = self._login('write-a@test.local', 'HesloA123')
        first = self._post(
            '/api/flow/kartoteka/zakaznici/',
            token,
            {'email': '  DUP@Write.TEST ', 'kontaktni_jmeno': 'Dana Dupová'},
        )
        self.assertEqual(first.status_code, 201)
        second = self._post(
            '/api/flow/kartoteka/zakaznici/',
            token,
            {'email': 'dup@write.test', 'kontaktni_jmeno': 'Jiná Dana'},
        )
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()['zakaznik']['uuid'], second.json()['zakaznik']['uuid'])
        self.assertEqual(
            Customer.objects.filter(salon=self.salon_a, email='dup@write.test').count(), 1,
        )

    def test_create_integrity_error_vraci_existujiciho(self):
        from unittest.mock import patch
        from django.db import IntegrityError
        token = self._login('write-a@test.local', 'HesloA123')
        with patch('flow.kartoteka_services.customer_for_email', side_effect=[None, self.eva]):
            with patch('flow.kartoteka_services.Customer.save', side_effect=IntegrityError('uniq')):
                r = self._post(
                    '/api/flow/kartoteka/zakaznici/',
                    token,
                    {'email': 'eva@write.test', 'kontaktni_jmeno': 'Eva Nová'},
                )
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json()['vytvoreno'])
        self.assertEqual(r.json()['zakaznik']['uuid'], str(self.eva.uuid))

    def test_create_archivovany_stejny_email_409(self):
        token = self._login('write-a@test.local', 'HesloA123')
        r = self._post(
            '/api/flow/kartoteka/zakaznici/',
            token,
            {'email': 'ARCHIV@write.test', 'kontaktni_jmeno': 'Arch Ivovaný'},
        )
        self.assertEqual(r.status_code, 409)
        self.assertFalse(r.json()['vytvoreno'])
        self.assertEqual(r.json()['zakaznik']['uuid'], str(self.archiv.uuid))
        self.assertEqual(r.json()['zakaznik']['stav'], 'archivovany')
        self.assertEqual(Customer.objects.filter(email='archiv@write.test', salon=self.salon_a).count(), 1)

    def test_create_cizi_rezervace_404(self):
        now = timezone.now()
        rez_b = Rezervace.objects.create(
            salon=self.salon_b,
            zamestnanec=self.owner_b,
            zacatek=now,
            konec=now + timedelta(hours=1),
            stav='potvrzeno',
            jmeno_host='Cizí',
            email_host='cizi-rez@write.test',
        )
        token = self._login('write-a@test.local', 'HesloA123')
        r = self._post('/api/flow/kartoteka/zakaznici/', token, {'rezervace_id': rez_b.id})
        self.assertEqual(r.status_code, 404)
        self.assertFalse(Customer.objects.filter(email='cizi-rez@write.test').exists())

    def test_create_neslucuje_jmeno_telefon(self):
        token = self._login('write-a@test.local', 'HesloA123')
        r = self._post(
            '/api/flow/kartoteka/zakaznici/',
            token,
            {
                'email': 'jiny-mail@write.test',
                'kontaktni_jmeno': 'Eva Nová',
                'telefon': '000',
            },
        )
        self.assertEqual(r.status_code, 201)
        self.assertNotEqual(r.json()['zakaznik']['uuid'], str(self.eva.uuid))

    def test_staff_smí_zapisovat(self):
        token = self._login('staff-a@test.local', 'StaffA123')
        r = self._post(
            '/api/flow/kartoteka/zakaznici/',
            token,
            {'email': 'staff-klient@write.test', 'kontaktni_jmeno': 'Klára Staffová'},
        )
        self.assertEqual(r.status_code, 201)
        cust = Customer.objects.get(uuid=r.json()['zakaznik']['uuid'])
        self.assertEqual(cust.vytvoril_id, self.staff_a.id)

    def test_entry_bez_objektu(self):
        token = self._login('write-a@test.local', 'HesloA123')
        r = self._post(
            f'/api/flow/kartoteka/zakaznici/{self.eva.uuid}/zapisy/',
            token,
            {'text': 'Kontrola, vše v pořádku.', 'objekt_uuid': None},
        )
        self.assertEqual(r.status_code, 201)
        self.assertIsNone(r.json()['objekt_uuid'])
        self.assertEqual(r.json()['typ_zapisu'], 'Poznámka')
        self.assertEqual(r.json()['autor'], 'Owner A')
        entry = Entry.objects.get(uuid=r.json()['uuid'])
        self.assertEqual(entry.zakaznik_id, self.eva.id)
        self.assertIsNone(entry.objekt_id)
        self.assertEqual(entry.vytvoril_id, self.owner_a.id)

    def test_entry_s_objektem(self):
        token = self._login('write-a@test.local', 'HesloA123')
        r = self._post(
            f'/api/flow/kartoteka/zakaznici/{self.eva.uuid}/zapisy/',
            token,
            {
                'text': 'Max je v pořádku.',
                'objekt_uuid': str(self.max.uuid),
                'nadpis': 'Kontrola',
                'typ_zapisu': 'Kontrola',
            },
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()['objekt_uuid'], str(self.max.uuid))
        self.assertEqual(r.json()['typ_zapisu'], 'Kontrola')
        self.assertEqual(r.json()['nadpis'], 'Kontrola')

    def test_entry_cizi_customer_404(self):
        token = self._login('write-a@test.local', 'HesloA123')
        r = self._post(
            f'/api/flow/kartoteka/zakaznici/{self.boris.uuid}/zapisy/',
            token,
            {'text': 'útok'},
        )
        self.assertEqual(r.status_code, 404)
        self.assertFalse(Entry.objects.filter(zakaznik=self.boris, text='útok').exists())

    def test_entry_cizi_object_404(self):
        token = self._login('write-a@test.local', 'HesloA123')
        r = self._post(
            f'/api/flow/kartoteka/zakaznici/{self.eva.uuid}/zapisy/',
            token,
            {'text': 'rex podstrčen', 'objekt_uuid': str(self.rex.uuid)},
        )
        self.assertEqual(r.status_code, 404)

    def test_entry_object_jineho_customer_stejny_salon_404(self):
        jiny = Customer.objects.create(
            salon=self.salon_a, prijmeni='Jiná', email='jina-obj@write.test',
        )
        micka = Object.objects.create(
            salon=self.salon_a, zakaznik=jiny, typ=self.typ_a, nazev='Micka',
        )
        token = self._login('write-a@test.local', 'HesloA123')
        r = self._post(
            f'/api/flow/kartoteka/zakaznici/{self.eva.uuid}/zapisy/',
            token,
            {'text': 'cizí pes', 'objekt_uuid': str(micka.uuid)},
        )
        self.assertEqual(r.status_code, 404)

    def test_entry_archivovany_409(self):
        token = self._login('write-a@test.local', 'HesloA123')
        r = self._post(
            f'/api/flow/kartoteka/zakaznici/{self.archiv.uuid}/zapisy/',
            token,
            {'text': 'nesmí'},
        )
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()['stav'], 'archivovany')

    def test_entry_prazdny_text_400(self):
        token = self._login('write-a@test.local', 'HesloA123')
        r = self._post(
            f'/api/flow/kartoteka/zakaznici/{self.eva.uuid}/zapisy/',
            token,
            {'text': '   '},
        )
        self.assertEqual(r.status_code, 400)

    def test_object_minimal(self):
        token = self._login('write-a@test.local', 'HesloA123')
        r = self._post(
            f'/api/flow/kartoteka/zakaznici/{self.eva.uuid}/objekty/',
            token,
            {'typ_uuid': str(self.typ_a.uuid), 'nazev': 'Micka'},
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()['nazev'], 'Micka')
        self.assertEqual(r.json()['typ_nazev'], 'Pes')
        obj = Object.objects.get(uuid=r.json()['uuid'])
        self.assertEqual(obj.zakaznik_id, self.eva.id)
        self.assertEqual(obj.typ_id, self.typ_a.id)
        self.assertEqual(obj.vytvoril_id, self.owner_a.id)
        from archivnik.models import CustomFieldValue
        self.assertEqual(CustomFieldValue.objects.filter(objekt=obj).count(), 0)

    def test_object_typ_bez_nazvu(self):
        token = self._login('write-a@test.local', 'HesloA123')
        r = self._post(
            f'/api/flow/kartoteka/zakaznici/{self.eva.uuid}/objekty/',
            token,
            {'typ_uuid': str(self.typ_bez_nazvu.uuid)},
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()['nazev'], '')

    def test_object_typ_vyzaduje_nazev(self):
        token = self._login('write-a@test.local', 'HesloA123')
        r = self._post(
            f'/api/flow/kartoteka/zakaznici/{self.eva.uuid}/objekty/',
            token,
            {'typ_uuid': str(self.typ_a.uuid), 'nazev': ''},
        )
        self.assertEqual(r.status_code, 400)

    def test_object_cizi_typ_404(self):
        token = self._login('write-a@test.local', 'HesloA123')
        r = self._post(
            f'/api/flow/kartoteka/zakaznici/{self.eva.uuid}/objekty/',
            token,
            {'typ_uuid': str(self.typ_b.uuid), 'nazev': 'Útok'},
        )
        self.assertEqual(r.status_code, 404)

    def test_object_cizi_customer_404(self):
        token = self._login('write-a@test.local', 'HesloA123')
        r = self._post(
            f'/api/flow/kartoteka/zakaznici/{self.boris.uuid}/objekty/',
            token,
            {'typ_uuid': str(self.typ_a.uuid), 'nazev': 'Útok'},
        )
        self.assertEqual(r.status_code, 404)

    def test_object_archivovany_409(self):
        token = self._login('write-a@test.local', 'HesloA123')
        r = self._post(
            f'/api/flow/kartoteka/zakaznici/{self.archiv.uuid}/objekty/',
            token,
            {'typ_uuid': str(self.typ_a.uuid), 'nazev': 'Max'},
        )
        self.assertEqual(r.status_code, 409)

    def test_object_typ_jineho_oboru_400(self):
        from archivnik.models import Obor
        vet = Obor.objects.create(salon=self.salon_a, nazev='Veterina', aktualni=True, poradi=1)
        pneu = Obor.objects.create(salon=self.salon_a, nazev='Pneu', aktualni=False, poradi=2)
        self.typ_a.obor = vet
        self.typ_a.save()
        self.typ_bez_nazvu.obor = vet
        self.typ_bez_nazvu.save()
        vuz = ObjectType.objects.create(
            salon=self.salon_a, obor=pneu, nazev='Osobní vůz', vyzaduje_nazev=True,
        )
        token = self._login('write-a@test.local', 'HesloA123')
        deny = self._post(
            f'/api/flow/kartoteka/zakaznici/{self.eva.uuid}/objekty/',
            token,
            {'typ_uuid': str(vuz.uuid), 'nazev': 'Octavia'},
        )
        self.assertEqual(deny.status_code, 400)
        ok = self._post(
            f'/api/flow/kartoteka/zakaznici/{self.eva.uuid}/objekty/',
            token,
            {'typ_uuid': str(self.typ_a.uuid), 'nazev': 'Rexík'},
        )
        self.assertEqual(ok.status_code, 201)
        typy = self.client.get('/api/flow/kartoteka/typy-objektu/', HTTP_X_FLOW_TOKEN=token)
        uuidy = {t['uuid'] for t in typy.json()}
        self.assertIn(str(self.typ_a.uuid), uuidy)
        self.assertNotIn(str(vuz.uuid), uuidy)
        self.assertNotIn(str(self.typ_b.uuid), uuidy)

    def test_typy_jen_vlastni_salon(self):
        token = self._login('write-a@test.local', 'HesloA123')
        r = self.client.get('/api/flow/kartoteka/typy-objektu/', HTTP_X_FLOW_TOKEN=token)
        uuidy = {t['uuid'] for t in r.json()}
        self.assertIn(str(self.typ_a.uuid), uuidy)
        self.assertNotIn(str(self.typ_b.uuid), uuidy)
