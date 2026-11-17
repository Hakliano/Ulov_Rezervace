import json

from django.test import TestCase, override_settings
from django.urls import reverse

from partner_admin.models import PotencialniKontakt


@override_settings(POSTAK_POTENCIALNI_API_TOKEN='test-token')
class PostakApiTests(TestCase):
    def setUp(self):
        self.h = {'HTTP_AUTHORIZATION': 'Bearer test-token'}

    def test_vyzaduje_token(self):
        r = self.client.get(reverse('partner_admin:postak_api_meta'))
        self.assertEqual(r.status_code, 401)

    def test_vytvoreni_a_konflikt(self):
        r = self.client.post(
            reverse('partner_admin:postak_api_potencialni'),
            data=json.dumps({'jmeno': 'Firma', 'email': 'novy@test.cz'}),
            content_type='application/json',
            **self.h,
        )
        self.assertEqual(r.status_code, 201)
        kid = r.json()['kontakt']['id']
        kontakt = PotencialniKontakt.objects.get(pk=kid)
        stare = kontakt.upraveno.isoformat()
        kontakt.jmeno = 'Jiné'
        kontakt.save()
        r2 = self.client.patch(
            reverse('partner_admin:postak_api_detail', args=[kid]),
            data=json.dumps({'jmeno': 'Conflict', 'email': 'novy@test.cz', 'expected_upraveno': stare}),
            content_type='application/json',
            **self.h,
        )
        self.assertEqual(r2.status_code, 409)

    def test_zmeny_od(self):
        PotencialniKontakt.objects.create(jmeno='A', email='a@test.cz')
        r = self.client.get(reverse('partner_admin:postak_api_zmeny'), **self.h)
        self.assertTrue(r.json()['ok'])
        self.assertGreaterEqual(len(r.json()['items']), 1)

    def test_create_uklada_adresni_pole(self):
        body = {
            'jmeno': 'Geo',
            'email': 'geo-create@test.cz',
            'mesto': 'Brno',
            'adresa': 'Ulice 1',
            'cast_obce': 'Střed',
            'latitude': 0,
            'longitude': 0,
        }
        r = self.client.post(
            reverse('partner_admin:postak_api_potencialni'),
            data=json.dumps(body),
            content_type='application/json',
            **self.h,
        )
        self.assertEqual(r.status_code, 201)
        k = PotencialniKontakt.objects.get(email='geo-create@test.cz')
        self.assertEqual(k.mesto, 'Brno')
        self.assertIsNone(k.latitude)
        self.assertIsNone(k.longitude)

    def test_patch_jen_telefon_field_conflict(self):
        kontakt = PotencialniKontakt.objects.create(
            jmeno='Firma', email='partial@test.cz', telefon='111', web='https://x.test'
        )
        stare_tel = kontakt.telefon
        kontakt.web = 'https://jine.test'
        kontakt.save()
        r = self.client.patch(
            reverse('partner_admin:postak_api_detail', args=[kontakt.pk]),
            data=json.dumps({
                'telefon': '222',
                'expected_fields': {'telefon': stare_tel},
            }),
            content_type='application/json',
            **self.h,
        )
        self.assertEqual(r.status_code, 200)
        kontakt.refresh_from_db()
        self.assertEqual(kontakt.telefon, '222')
        self.assertEqual(kontakt.web, 'https://jine.test')

    def test_patch_field_conflict_stejne_pole(self):
        kontakt = PotencialniKontakt.objects.create(jmeno='X', email='conflict2@test.cz', telefon='111')
        stare = kontakt.telefon
        kontakt.telefon = '999'
        kontakt.save()
        r = self.client.patch(
            reverse('partner_admin:postak_api_detail', args=[kontakt.pk]),
            data=json.dumps({
                'telefon': '222',
                'expected_fields': {'telefon': stare},
            }),
            content_type='application/json',
            **self.h,
        )
        self.assertEqual(r.status_code, 409)
        self.assertIn('telefon', r.json().get('fields', []))

    def test_zmeny_strankuje_bez_since(self):
        for i in range(3):
            PotencialniKontakt.objects.create(jmeno=f'B{i}', email=f'page{i}@test.cz')
        r1 = self.client.get(reverse('partner_admin:postak_api_zmeny'), {'limit': 2, 'offset': 0}, **self.h)
        r2 = self.client.get(reverse('partner_admin:postak_api_zmeny'), {'limit': 2, 'offset': 2}, **self.h)
        j1, j2 = r1.json(), r2.json()
        self.assertTrue(j1['has_more'])
        self.assertEqual(len(j1['items']), 2)
        ids = {x['id'] for x in j1['items'] + j2['items']}
        self.assertGreaterEqual(len(ids), 3)
