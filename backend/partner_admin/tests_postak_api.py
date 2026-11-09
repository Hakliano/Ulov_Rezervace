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
