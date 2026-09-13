"""P0: Archivník funguje bez FLOW a drží tenant izolaci."""

from datetime import date
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import Count
from django.test import TestCase
from PIL import Image
from rest_framework.test import APIClient

from archivnik.models import Asset, CustomFieldDef, Customer, Entry, Object, ObjectType, Reminder
from flow.models import FlowSession, FlowUser
from partner_admin.models import MODUL_ARCHIVNIK, ModulKatalog, PartnerModul
from rezervace.models import Zamestnanec
from salons.models import Salon


def _zapni_archivnik(salon):
    katalog, _ = ModulKatalog.objects.get_or_create(
        kod=MODUL_ARCHIVNIK,
        defaults={
            'nazev': 'Archivník',
            'popis': 'Digitální kartotéka.',
            'razeni': 20,
        },
    )
    PartnerModul.objects.update_or_create(
        salon=salon,
        modul=katalog,
        defaults={'status': PartnerModul.STAV_ACTIVE},
    )
    return katalog


def _salon_s_majitelem(name, email, password='archivnik123'):
    salon = Salon.objects.create(name=name, email=email)
    owner = Zamestnanec.objects.create(
        salon=salon,
        jmeno=f'Majitel {name}',
        role=Zamestnanec.ROLE_MAJITEL,
        prihlasovaci_jmeno=email,
        aktivni=True,
        zobrazit_na_webu=False,
    )
    owner.set_password(password)
    owner.save(update_fields=['password_hash'])
    return salon, owner


class ArchivnikStandaloneTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.salon, self.owner = _salon_s_majitelem('Archivník sólo', 'solo@archivnik.test')
        _zapni_archivnik(self.salon)

    def test_login_bez_flow_user(self):
        self.assertFalse(FlowUser.objects.filter(salon=self.salon).exists())
        res = self.client.post(
            '/api/archivnik/auth/login/',
            {'email': 'solo@archivnik.test', 'password': 'archivnik123'},
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data['token'])
        self.assertEqual(res.data['provozovna'], 'Archivník sólo')
        self.assertFalse(FlowUser.objects.filter(salon=self.salon).exists())
        self.assertEqual(FlowSession.objects.count(), 0)

    def test_modul_vypnuty_vraci_403(self):
        PartnerModul.objects.filter(salon=self.salon, modul__kod=MODUL_ARCHIVNIK).update(
            status=PartnerModul.STAV_INACTIVE,
        )
        res = self.client.post(
            '/api/archivnik/auth/login/',
            {'email': 'solo@archivnik.test', 'password': 'archivnik123'},
            format='json',
        )
        self.assertEqual(res.status_code, 403)

    def test_spatne_heslo_401(self):
        res = self.client.post(
            '/api/archivnik/auth/login/',
            {'email': 'solo@archivnik.test', 'password': 'spatne'},
            format='json',
        )
        self.assertEqual(res.status_code, 401)


class ArchivnikTenantIsolationTests(TestCase):
    def setUp(self):
        self.a_client = APIClient()
        self.b_client = APIClient()
        self.salon_a, self.owner_a = _salon_s_majitelem('Tenant A', 'a@archivnik.test')
        self.salon_b, self.owner_b = _salon_s_majitelem('Tenant B', 'b@archivnik.test')
        _zapni_archivnik(self.salon_a)
        _zapni_archivnik(self.salon_b)
        token_a = self.a_client.post(
            '/api/archivnik/auth/login/',
            {'email': 'a@archivnik.test', 'password': 'archivnik123'},
            format='json',
        ).data['token']
        token_b = self.b_client.post(
            '/api/archivnik/auth/login/',
            {'email': 'b@archivnik.test', 'password': 'archivnik123'},
            format='json',
        ).data['token']
        self.a_client.credentials(HTTP_X_ARCHIVNIK_TOKEN=token_a)
        self.b_client.credentials(HTTP_X_ARCHIVNIK_TOKEN=token_b)
        self.zakaznik_a = Customer.objects.create(
            salon=self.salon_a, prijmeni='Novák', jmeno='Adam', telefon='777111222',
        )
        self.zakaznik_b = Customer.objects.create(
            salon=self.salon_b, prijmeni='Novák', jmeno='Boris', telefon='777333444',
        )

    def test_tenant_a_nevidi_zakaznika_b(self):
        seznam = self.a_client.get('/api/archivnik/customers/')
        self.assertEqual(seznam.status_code, 200)
        uuidy = {row['uuid'] for row in seznam.data}
        self.assertIn(str(self.zakaznik_a.uuid), uuidy)
        self.assertNotIn(str(self.zakaznik_b.uuid), uuidy)

        detail = self.a_client.get(f'/api/archivnik/customers/{self.zakaznik_b.uuid}/')
        self.assertEqual(detail.status_code, 404)

    def test_hledani_nevraci_cizi_tenant(self):
        res = self.a_client.get('/api/archivnik/search/', {'q': 'Novák'})
        self.assertEqual(res.status_code, 200)
        jmena = {z['jmeno'] for z in res.data['zakaznici']}
        self.assertEqual(jmena, {'Adam'})


class ArchivnikEntryModelTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.salon, self.owner = _salon_s_majitelem('Kartotéka', 'karta@archivnik.test')
        _zapni_archivnik(self.salon)
        token = self.client.post(
            '/api/archivnik/auth/login/',
            {'email': 'karta@archivnik.test', 'password': 'archivnik123'},
            format='json',
        ).data['token']
        self.client.credentials(HTTP_X_ARCHIVNIK_TOKEN=token)
        self.typ = ObjectType.objects.create(salon=self.salon, nazev='Vozidlo')
        self.zakaznik = Customer.objects.create(
            salon=self.salon, prijmeni='Svoboda', jmeno='Eva', email='eva@test.local',
        )
        self.jiny = Customer.objects.create(salon=self.salon, prijmeni='Dvořák', jmeno='Jan')
        self.objekt = Object.objects.create(
            salon=self.salon, zakaznik=self.zakaznik, typ=self.typ, nazev='Škoda Octavia',
        )

    def test_zapis_jen_k_zakaznikovi(self):
        res = self.client.post(
            '/api/archivnik/entries/',
            {'zakaznik_uuid': str(self.zakaznik.uuid), 'text': 'Preferuje e-mail.'},
            format='json',
        )
        self.assertEqual(res.status_code, 201)
        self.assertIsNone(res.data['objekt_uuid'])
        self.assertEqual(res.data['zakaznik_uuid'], str(self.zakaznik.uuid))

    def test_zapis_k_objektu(self):
        res = self.client.post(
            '/api/archivnik/entries/',
            {'objekt_uuid': str(self.objekt.uuid), 'text': 'STK do června.'},
            format='json',
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data['objekt_uuid'], str(self.objekt.uuid))
        self.assertEqual(res.data['zakaznik_uuid'], str(self.zakaznik.uuid))
        self.client.post(
            '/api/archivnik/entries/',
            {'zakaznik_uuid': str(self.zakaznik.uuid), 'text': 'Jen k majiteli.'},
            format='json',
        )
        kombinace = self.client.get(
            f'/api/archivnik/entries/?zakaznik={self.zakaznik.uuid}&vcetne_objektu=1'
        )
        self.assertEqual(len(kombinace.data), 2)
        jen_objekt = self.client.get(f'/api/archivnik/entries/?objekt={self.objekt.uuid}')
        self.assertEqual(len(jen_objekt.data), 1)

    def test_cizi_objekt_u_jineho_zakaznika_400(self):
        res = self.client.post(
            '/api/archivnik/entries/',
            {
                'zakaznik_uuid': str(self.jiny.uuid),
                'objekt_uuid': str(self.objekt.uuid),
                'text': 'Nesmí projít.',
            },
            format='json',
        )
        self.assertEqual(res.status_code, 400)

    def test_hledani_jmeno_telefon_email_objekt_typ(self):
        Customer.objects.create(
            salon=self.salon, prijmeni='Horák', jmeno='Petr', telefon='608999000',
            email='petr@example.test',
        )
        res = self.client.get('/api/archivnik/search/', {'q': '608999000'})
        self.assertEqual(len(res.data['zakaznici']), 1)
        res = self.client.get('/api/archivnik/search/', {'q': 'petr@example.test'})
        self.assertEqual(len(res.data['zakaznici']), 1)
        res = self.client.get('/api/archivnik/search/', {'q': 'Octavia'})
        self.assertEqual(len(res.data['objekty']), 1)
        res = self.client.get('/api/archivnik/search/', {'q': 'Vozidlo'})
        self.assertEqual(len(res.data['objekty']), 1)

    def test_pripominka_a_overview_pocty(self):
        Reminder.objects.create(
            salon=self.salon,
            zakaznik=self.zakaznik,
            termin=date(2030, 1, 15),
            text='Kontrola',
        )
        res = self.client.get('/api/archivnik/overview/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['zakaznici'], 2)
        self.assertEqual(res.data['objekty'], 1)
        self.assertEqual(res.data['pripominky_aktivni'], 1)
        self.assertEqual(res.data['podle_typu'][0]['typ'], 'Vozidlo')
        self.assertEqual(res.data['nejblizsi_pripominky'][0]['text'], 'Kontrola')

        obj = self.client.get('/api/archivnik/objects/').data[0]
        self.assertEqual(obj['zapisy_pocet'], 0)
        self.assertEqual(obj['pripominky_aktivni'], 0)

        self.client.post(
            '/api/archivnik/entries/',
            {'objekt_uuid': str(self.objekt.uuid), 'text': 'Poznámka k vozu.'},
            format='json',
        )
        obj = self.client.get(f'/api/archivnik/objects/{self.objekt.uuid}/').data
        self.assertEqual(obj['zapisy_pocet'], 1)
        self.assertTrue(obj['posledni_zapis'])

        u_zak = self.client.get(
            f'/api/archivnik/reminders/?stav=aktivni&zakaznik={self.zakaznik.uuid}'
        )
        self.assertEqual(len(u_zak.data), 1)
        u_obj = self.client.get(
            f'/api/archivnik/reminders/?stav=aktivni&objekt={self.objekt.uuid}'
        )
        self.assertEqual(len(u_obj.data), 0)


class SeedArchivnikOnlyTests(TestCase):
    def test_seed_vytvori_provozovnu_bez_aktivniho_flow(self):
        from django.core.management import call_command

        from archivnik.management.commands.seed_archivnik_only import OWNER_EMAIL, OWNER_PASSWORD

        call_command('seed_archivnik_only')
        call_command('seed_archivnik_only')
        owners = Zamestnanec.objects.filter(
            prihlasovaci_jmeno__iexact=OWNER_EMAIL,
            role=Zamestnanec.ROLE_MAJITEL,
        )
        self.assertEqual(owners.count(), 1)
        salon = owners.get().salon
        self.assertFalse(FlowUser.objects.filter(salon=salon, aktivni=True).exists())
        self.assertEqual(FlowSession.objects.filter(user__salon=salon).count(), 0)
        self.assertTrue(
            PartnerModul.objects.filter(
                salon=salon, modul__kod=MODUL_ARCHIVNIK, status=PartnerModul.STAV_ACTIVE,
            ).exists()
        )
        client = APIClient()
        res = client.post(
            '/api/archivnik/auth/login/',
            {'email': OWNER_EMAIL, 'password': OWNER_PASSWORD},
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data['provozovna'], 'Archivník sólo')
        self.assertGreaterEqual(Customer.objects.filter(salon=salon).count(), 10)
        self.assertGreaterEqual(Object.objects.filter(salon=salon).count(), 15)
        self.assertGreaterEqual(ObjectType.objects.filter(salon=salon).count(), 3)
        self.assertTrue(Entry.objects.filter(salon=salon, objekt__isnull=True).exists())
        self.assertTrue(Entry.objects.filter(salon=salon, objekt__isnull=False).exists())
        self.assertTrue(Reminder.objects.filter(salon=salon).exists())
        self.assertTrue(CustomFieldDef.objects.filter(salon=salon).exists())
        self.assertTrue(Asset.objects.filter(salon=salon, objekt__isnull=False).exists())
        self.assertTrue(Asset.objects.filter(salon=salon, objekt__isnull=True).exists())
        self.assertTrue(Asset.objects.filter(salon=salon, zapis__isnull=False).exists())
        self.assertTrue(
            Customer.objects.filter(salon=salon).annotate(n=Count('objekty')).filter(n=1).exists()
        )
        self.assertTrue(
            Customer.objects.filter(salon=salon).annotate(n=Count('objekty')).filter(n__gte=2).exists()
        )


def _png_file(name='foto.png', color=(20, 80, 60)):
    buf = BytesIO()
    Image.new('RGB', (80, 80), color).save(buf, format='PNG')
    return SimpleUploadedFile(name, buf.getvalue(), content_type='image/png')


class ArchivnikEvidenceTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.salon, self.owner = _salon_s_majitelem('Evidence', 'evidence@archivnik.test')
        _zapni_archivnik(self.salon)
        token = self.client.post(
            '/api/archivnik/auth/login/',
            {'email': 'evidence@archivnik.test', 'password': 'archivnik123'},
            format='json',
        ).data['token']
        self.client.credentials(HTTP_X_ARCHIVNIK_TOKEN=token)
        self.typ = ObjectType.objects.create(salon=self.salon, nazev='Vozidlo')
        self.zakaznik = Customer.objects.create(salon=self.salon, prijmeni='Novák', jmeno='Eva')
        self.objekt = Object.objects.create(
            salon=self.salon, zakaznik=self.zakaznik, typ=self.typ, nazev='Octavia',
        )

    def test_vlastni_pole_podle_typu_ne_segmentu(self):
        res = self.client.post(
            '/api/archivnik/fields/',
            {'typ_uuid': str(self.typ.uuid), 'nazev': 'VIN', 'druh': 'text'},
            format='json',
        )
        self.assertEqual(res.status_code, 201)
        put = self.client.put(
            f'/api/archivnik/objects/{self.objekt.uuid}/fields/',
            {'hodnoty': [{'pole_uuid': res.data['uuid'], 'hodnota': 'TMB123'}]},
            format='json',
        )
        self.assertEqual(put.status_code, 200)
        self.assertEqual(put.data[0]['hodnota'], 'TMB123')

    def test_priloha_zapisu_je_jeden_asset_i_v_dokumentaci(self):
        entry = self.client.post(
            '/api/archivnik/entries/',
            {'objekt_uuid': str(self.objekt.uuid), 'text': 'Kontrola kulhání.', 'nadpis': 'Vyšetření'},
            format='json',
        )
        self.assertEqual(entry.status_code, 201)
        upload = self.client.post(
            '/api/archivnik/assets/',
            {
                'soubor': _png_file('laborator.png'),
                'zapis_uuid': entry.data['uuid'],
                'druh': 'fotografie',
                'nazev': 'laborator.png',
            },
            format='multipart',
        )
        self.assertEqual(upload.status_code, 201, upload.data)
        asset_uuid = upload.data['uuid']
        self.assertEqual(upload.data['zapis_uuid'], entry.data['uuid'])
        self.assertEqual(upload.data['objekt_uuid'], str(self.objekt.uuid))

        u_zapisu = self.client.get(f'/api/archivnik/entries/?objekt={self.objekt.uuid}')
        self.assertEqual(u_zapisu.data[0]['prilohy'][0]['uuid'], asset_uuid)

        u_objektu = self.client.get(f'/api/archivnik/assets/?objekt={self.objekt.uuid}')
        self.assertEqual({row['uuid'] for row in u_objektu.data}, {asset_uuid})

        content = self.client.get(f'/api/archivnik/assets/{asset_uuid}/content/')
        self.assertEqual(content.status_code, 200)
        self.assertTrue(content.content.startswith(b'\x89PNG'))

    def test_asset_u_zakaznika_bez_objektu(self):
        res = self.client.post(
            '/api/archivnik/assets/',
            {
                'soubor': SimpleUploadedFile(
                    'smlouva.pdf', b'%PDF-1.1\ntrailer<</Root 1 0 R>>\n%%EOF',
                    content_type='application/pdf',
                ),
                'zakaznik_uuid': str(self.zakaznik.uuid),
                'druh': 'dokument',
                'nazev': 'smlouva.pdf',
            },
            format='multipart',
        )
        self.assertEqual(res.status_code, 201, res.data)
        self.assertIsNone(res.data['objekt_uuid'])
        self.assertEqual(res.data['zakaznik_uuid'], str(self.zakaznik.uuid))

    def test_cizi_tenant_nesmi_cist_soubor(self):
        other_client = APIClient()
        salon_b, _owner_b = _salon_s_majitelem('Cizí', 'cizi-ev@archivnik.test')
        _zapni_archivnik(salon_b)
        token_b = other_client.post(
            '/api/archivnik/auth/login/',
            {'email': 'cizi-ev@archivnik.test', 'password': 'archivnik123'},
            format='json',
        ).data['token']
        other_client.credentials(HTTP_X_ARCHIVNIK_TOKEN=token_b)
        created = self.client.post(
            '/api/archivnik/assets/',
            {
                'soubor': _png_file(),
                'objekt_uuid': str(self.objekt.uuid),
                'druh': 'fotografie',
            },
            format='multipart',
        )
        self.assertEqual(created.status_code, 201)
        stolen = other_client.get(f'/api/archivnik/assets/{created.data["uuid"]}/content/')
        self.assertEqual(stolen.status_code, 404)
        listed = other_client.get('/api/archivnik/assets/')
        self.assertEqual(listed.data, [])

