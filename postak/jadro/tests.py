from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

HESLO = 'Spravne-heslo-1'
NOVE = 'Druhe-heslo-22'

STRANKY = ['prehled', 'emaily', 'klienti', 'kalendar', 'dokumentace', 'nastaveni']


def uzivatel(username, *, superuser=False, password=HESLO):
    user = User.objects.create_user(username, password=password)
    if superuser:
        user.is_superuser = True
        user.save(update_fields=['is_superuser'])
    return user


class AuthTests(TestCase):
    def test_anonym_nevidi_vnitrni_stranky(self):
        for name in STRANKY + ['uzivatele', 'uzivatel_novy']:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 302, name)
            self.assertIn('/prihlaseni/', response.url)

        detail = self.client.get(reverse('uzivatel_detail', args=[1]))
        self.assertEqual(detail.status_code, 302)
        self.assertEqual(self.client.get(reverse('prihlaseni')).status_code, 200)

    def test_prihlaseni_a_odhlaseni(self):
        uzivatel('eva')
        self.assertFalse(self.client.login(username='eva', password='spatne'))
        self.assertTrue(self.client.login(username='eva', password=HESLO))
        self.assertEqual(self.client.get(reverse('prehled')).status_code, 200)
        self.assertRedirects(self.client.post(reverse('odhlaseni')), reverse('prihlaseni'))
        self.assertEqual(self.client.get(reverse('emaily')).status_code, 302)

    def test_sekce_a_prazdne_stavy(self):
        self.client.force_login(uzivatel('eva'))
        for name in STRANKY:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200, name)
            self.assertNotContains(response, '3 000')
        self.assertContains(self.client.get(reverse('emaily')), 'žádná pošta')
        self.assertContains(self.client.get(reverse('klienti')), 'zatím prázdný')

    def test_user_nespravuje_uzivatele(self):
        eva = uzivatel('eva')
        self.client.force_login(eva)
        self.assertEqual(self.client.get(reverse('uzivatele')).status_code, 403)
        self.assertEqual(self.client.get(reverse('uzivatel_novy')).status_code, 403)
        self.assertEqual(self.client.get(reverse('uzivatel_detail', args=[eva.pk])).status_code, 403)
        self.assertNotContains(self.client.get(reverse('nastaveni')), 'Správa uživatelů')

    def test_superuser_vytvori_a_deaktivuje(self):
        self.client.force_login(uzivatel('admin', superuser=True))
        response = self.client.post(reverse('uzivatel_novy'), {
            'username': 'eva',
            'first_name': 'Eva',
            'role': 'user',
            'password1': HESLO,
            'password2': HESLO,
        })
        eva = User.objects.get(username='eva')
        self.assertRedirects(response, reverse('uzivatele'))
        self.assertFalse(eva.is_superuser)
        self.assertTrue(eva.is_active)

        response = self.client.post(reverse('uzivatel_detail', args=[eva.pk]), {'akce': 'deaktivovat'})
        self.assertRedirects(response, reverse('uzivatel_detail', args=[eva.pk]))
        eva.refresh_from_db()
        self.assertFalse(eva.is_active)
        self.client.logout()
        self.assertFalse(self.client.login(username='eva', password=HESLO))

        self.client.force_login(User.objects.get(username='admin'))
        self.client.post(reverse('uzivatel_detail', args=[eva.pk]), {'akce': 'aktivovat'})
        eva.refresh_from_db()
        self.assertTrue(eva.is_active)

    def test_slabe_heslo_se_neulozi(self):
        self.client.force_login(uzivatel('admin', superuser=True))
        response = self.client.post(reverse('uzivatel_novy'), {
            'username': 'eva',
            'role': 'user',
            'password1': '123',
            'password2': '123',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='eva').exists())

    def test_vlastni_heslo_a_reset_adminem(self):
        eva = uzivatel('eva')
        admin = uzivatel('admin', superuser=True)
        self.client.force_login(eva)
        response = self.client.post(reverse('nastaveni'), {
            'old_password': HESLO,
            'new_password1': NOVE,
            'new_password2': NOVE,
        })
        self.assertRedirects(response, reverse('nastaveni'))
        self.assertTrue(self.client.login(username='eva', password=NOVE))

        self.client.force_login(admin)
        response = self.client.post(reverse('uzivatel_detail', args=[eva.pk]), {
            'akce': 'heslo',
            'new_password1': HESLO,
            'new_password2': HESLO,
        })
        self.assertRedirects(response, reverse('uzivatel_detail', args=[eva.pk]))
        self.assertTrue(self.client.login(username='eva', password=HESLO))
        self.assertFalse(self.client.login(username='eva', password=NOVE))

    def test_posledni_superuser_zustava(self):
        admin = uzivatel('admin', superuser=True)
        self.client.force_login(admin)
        self.client.post(reverse('uzivatel_detail', args=[admin.pk]), {'akce': 'deaktivovat'})
        self.client.post(reverse('uzivatel_detail', args=[admin.pk]), {'akce': 'role', 'role': 'user'})
        admin.refresh_from_db()
        self.assertTrue(admin.is_active)
        self.assertTrue(admin.is_superuser)


@override_settings(POSTAK_PREFIX='/postak')
class PrefixTests(TestCase):
    def test_prefix_i_zkracena_cesta(self):
        self.client.force_login(uzivatel('eva'))
        prime = self.client.get('/postak/emaily/')
        self.assertEqual(prime.status_code, 200)
        self.assertContains(prime, 'href="/postak/klienti/"')
        self.assertContains(prime, 'href="/postak/static/postak.css"')
        zkracene = self.client.get('/kalendar/')
        self.assertEqual(zkracene.status_code, 200)
        self.assertContains(zkracene, 'href="/postak/dokumentace/"')

        anonym = self.client
        anonym.logout()
        response = anonym.get('/postak/')
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/postak/prihlaseni/'))

    def test_statika_s_prefixem_i_bez(self):
        with_prefix = self.client.get('/postak/static/postak.css')
        bare = self.client.get('/static/postak.css')
        self.assertEqual(with_prefix.status_code, 200)
        self.assertEqual(bare.status_code, 200)
        self.assertIn(b'.card', b''.join(with_prefix.streaming_content))
