from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from partner_admin.models import PotencialniKontakt, PotencialniSektor
from partner_admin.potencialni import importuj_kontakty, normalizuj_radek
from salons.models import Salon


VZOROVY_JSON = '''[
  {
    "email": "xxxx@xxx.cz",
    "company_name": "VET - MVDr. Martin Ježek",
    "ico": "",
    "phone": "+420 241 401 000, +420 724 127 404",
    "address": "",
    "description": "Boleslavova 1525/20, 140 00 Praha-Nusle, okres Praha 4",
    "email_template": "",
    "status": "contacted"
  },
  {
    "email": "info@veterina-havirov.cz",
    "company_name": "VET - Veterinární ordinace u Nemocnice",
    "ico": "",
    "phone": "596 810 050, 603 842 823",
    "address": "",
    "description": "Astronautů 5, 736 01 Havířov, okres Karviná",
    "email_template": "",
    "status": "lead"
  }
]'''


class PotencialniKlientiTests(TestCase):
    def setUp(self):
        self.superuser = get_user_model().objects.create_superuser(
            username='superadmin',
            email='admin@example.test',
            password='bezpecne-test-heslo',
        )
        self.url = reverse('partner_admin:potencialni')

    def test_model_nema_vazbu_na_salon(self):
        jmena = {f.name for f in PotencialniKontakt._meta.get_fields()}
        self.assertNotIn('salon', jmena)
        Salon.objects.create(name='Tarifový partner', email='partner@example.test')
        self.assertEqual(PotencialniKontakt.objects.count(), 0)

    def test_email_je_unikatni(self):
        sektor = PotencialniSektor.objects.get(nazev='nezařazeno')
        PotencialniKontakt.objects.create(
            jmeno='A', email='dup@example.test', sektor=sektor,
        )
        with self.assertRaises(IntegrityError):
            PotencialniKontakt.objects.create(
                jmeno='B', email='DUP@example.test', sektor=sektor,
            )

    def test_import_vzoroveho_json_ignoruje_stav_a_mapuje_vet(self):
        vysledek = importuj_kontakty(VZOROVY_JSON)
        self.assertEqual(vysledek['vytvoreno'], 2)
        jezek = PotencialniKontakt.objects.get(email='xxxx@xxx.cz')
        self.assertEqual(jezek.stav, PotencialniKontakt.STAV_LEAD_PRED)
        self.assertEqual(jezek.sektor.nazev, 'Veterina')
        self.assertIn('Boleslavova', jezek.adresa)
        self.assertEqual(jezek.poznamka, '')
        havirov = PotencialniKontakt.objects.get(email='info@veterina-havirov.cz')
        self.assertEqual(havirov.stav, 'lead_pred_webu')
        self.assertEqual(havirov.sektor.nazev, 'Veterina')
        znovu = importuj_kontakty(VZOROVY_JSON)
        self.assertEqual(znovu['vytvoreno'], 0)
        self.assertEqual(znovu['duplicita'], 2)

    def test_salon_prefix_a_nezarazeno(self):
        importuj_kontakty([
            {
                'email': 'krasa@example.test',
                'company_name': 'SALON - Studio Krása',
                'status': 'contacted',
                'website': 'https://krasa.cz',
            },
            {
                'jmeno': 'Autoservis Novák',
                'email': 'servis@example.test',
            },
        ])
        salon = PotencialniKontakt.objects.get(email='krasa@example.test')
        self.assertEqual(salon.sektor.nazev, 'Beauty')
        self.assertEqual(salon.stav, PotencialniKontakt.STAV_LEAD_PRED)
        self.assertEqual(salon.web, 'https://krasa.cz')
        servis = PotencialniKontakt.objects.get(email='servis@example.test')
        self.assertEqual(servis.sektor.nazev, 'nezařazeno')

    def test_stranka_jen_pro_superadmina(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)
        obycejny = get_user_model().objects.create_user(
            username='ops', password='heslo-12345',
        )
        self.client.force_login(obycejny)
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.client.force_login(self.superuser)
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Potenciální klienti')
        self.assertContains(res, 'company_name')
        self.assertNotContains(res, 'Tarifový partner')

    def test_manual_pridani_filtry_stav_sektor_export(self):
        self.client.force_login(self.superuser)
        beauty = PotencialniSektor.objects.get(nazev='Beauty')
        pridat = self.client.post(reverse('partner_admin:potencialni_pridat'), {
            'jmeno': 'Studio Luna',
            'email': 'luna@example.test',
            'telefon': '+420 777 111 222',
            'web_new': 'https://luna.cz',
            'sektor_id': str(beauty.id),
        })
        self.assertEqual(pridat.status_code, 302)
        kontakt = PotencialniKontakt.objects.get(email='luna@example.test')
        self.assertEqual(kontakt.stav, PotencialniKontakt.STAV_LEAD_PRED)
        self.assertEqual(kontakt.sektor.nazev, 'Beauty')

        seznam = self.client.get(self.url, {'q': 'Luna', 'web': 'ano', 'telefon': 'ano'})
        self.assertContains(seznam, 'Studio Luna')
        prazdny = self.client.get(self.url, {'web': 'ne'})
        self.assertNotContains(prazdny, 'Studio Luna')

        ajax = self.client.post(
            reverse('partner_admin:potencialni_stav', args=[kontakt.id]),
            {'stav': PotencialniKontakt.STAV_MA_ZAJEM},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(ajax.json()['ok'], True)
        kontakt.refresh_from_db()
        self.assertEqual(kontakt.stav, PotencialniKontakt.STAV_MA_ZAJEM)

        self.client.post(reverse('partner_admin:potencialni_ulozit', args=[kontakt.id]), {
            'jmeno': 'Studio Luna',
            'email': 'luna@example.test',
            'web_new': 'https://luna-new.cz',
            'poznamka': 'zavolat v pondělí',
            'sektor_id': str(beauty.id),
        })
        kontakt.refresh_from_db()
        self.assertEqual(kontakt.web, 'https://luna-new.cz')
        self.assertIn('pondělí', kontakt.poznamka)

        self.client.post(reverse('partner_admin:potencialni_sektor'), {
            'sektor_nazev': 'Dental',
        })
        self.assertTrue(PotencialniSektor.objects.filter(nazev='Dental').exists())

        export = self.client.get(reverse('partner_admin:potencialni_export'))
        self.assertEqual(export['Content-Type'], 'application/json; charset=utf-8')
        self.assertIn('luna@example.test', export.content.decode())

    def test_normalizace_aliasu(self):
        data = normalizuj_radek({
            'mail': 'Alias@Example.TEST',
            'nazev': 'Firma s.r.o.',
            'tel': '123',
            'url': 'https://firma.cz',
        })
        self.assertEqual(data['email'], 'alias@example.test')
        self.assertEqual(data['jmeno'], 'Firma s.r.o.')
        self.assertEqual(data['stav'], PotencialniKontakt.STAV_LEAD_PRED)
        self.assertEqual(data['sektor'].nazev, 'nezařazeno')


    def test_upravit_zustane_na_strance_a_pager_okna(self):
        from partner_admin.potencialni import cisla_stranek

        self.assertEqual(
            cisla_stranek(12, 33),
            [1, None, 10, 11, 12, 13, 14, None, 33],
        )
        self.client.force_login(self.superuser)
        sektor = PotencialniSektor.objects.get(nazev='nezařazeno')
        for i in range(55):
            PotencialniKontakt.objects.create(
                jmeno=f'Kontakt {i:03d}',
                email=f'k{i:03d}@example.test',
                sektor=sektor,
            )
        stary = PotencialniKontakt.objects.order_by('id').first()
        strana2 = self.client.get(self.url, {'stranka': '2'})
        self.assertContains(strana2, stary.jmeno)
        self.assertContains(strana2, f'stranka=2&amp;edit={stary.id}')
        self.assertContains(strana2, 'Jít na')

        edit = self.client.get(self.url, {'edit': str(stary.id)})
        self.assertContains(edit, 'Uložit změny')
        self.assertContains(edit, stary.jmeno)
        self.assertContains(edit, 'is-editing')

    def test_rychle_pridani_webu(self):
        self.client.force_login(self.superuser)
        kontakt = PotencialniKontakt.objects.create(
            jmeno='Bez webu',
            email='bezwebu@example.test',
            sektor=PotencialniSektor.objects.get(nazev='nezařazeno'),
        )
        seznam = self.client.get(self.url)
        self.assertContains(seznam, '+ Web')
        uloz = self.client.post(
            reverse('partner_admin:potencialni_web', args=[kontakt.id]),
            {'web_new': 'https://salon.cz'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(uloz.json()['web'], 'https://salon.cz')
        kontakt.refresh_from_db()
        self.assertEqual(kontakt.web, 'https://salon.cz')

    def test_graf_stavu_procenta(self):
        self.client.force_login(self.superuser)
        sektor = PotencialniSektor.objects.get(nazev='nezařazeno')
        PotencialniKontakt.objects.create(
            jmeno='A', email='a-graf@example.test', sektor=sektor,
        )
        druhy = PotencialniKontakt.objects.create(
            jmeno='B', email='b-graf@example.test', sektor=sektor,
            stav=PotencialniKontakt.STAV_MA_ZAJEM,
        )
        html = self.client.get(self.url).content.decode()
        self.assertIn('Stavy ze všech kontaktů', html)
        self.assertIn('width: 50.0000%', html)
        self.assertIn(druhy.get_stav_display(), html)
