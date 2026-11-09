import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
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


@override_settings(POSTAK_PREFIX='')
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
        emaily = self.client.get(reverse('emaily'))
        self.assertIn(emaily.status_code, (200, 302))
        from unittest.mock import patch
        with patch('jadro.klienti_views._fetch_meta', return_value=([], [], [])):
            self.assertContains(self.client.get(reverse('klienti')), 'SYNCHRONIZOVAT KLIENTY')

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
            'akce': 'heslo',
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

    def test_superuser_upravi_jmeno_a_email(self):
        self.client.force_login(uzivatel('admin', superuser=True))
        eva = uzivatel('eva')
        response = self.client.post(reverse('uzivatel_detail', args=[eva.pk]), {
            'akce': 'ucet',
            'username': 'eva.nova',
            'email': 'Eva@Firma.cz',
            'first_name': 'Eva Nová',
        })
        self.assertRedirects(response, reverse('uzivatel_detail', args=[eva.pk]))
        eva.refresh_from_db()
        self.assertEqual(eva.username, 'eva.nova')
        self.assertEqual(eva.email, 'eva@firma.cz')
        self.assertEqual(eva.first_name, 'Eva Nová')
        self.assertTrue(self.client.login(username='eva.nova', password=HESLO))
        self.client.force_login(User.objects.get(username='admin'))

        kolize = self.client.post(reverse('uzivatel_detail', args=[eva.pk]), {
            'akce': 'ucet',
            'username': 'admin',
            'email': 'eva@firma.cz',
            'first_name': 'Eva Nová',
        })
        self.assertEqual(kolize.status_code, 200)
        eva.refresh_from_db()
        self.assertEqual(eva.username, 'eva.nova')

    def test_uzivatel_meni_jen_svuj_profil(self):
        eva = uzivatel('eva')
        jiri = uzivatel('jiri')
        self.client.force_login(eva)
        response = self.client.post(reverse('nastaveni'), {
            'akce': 'profil',
            'email': 'eva@posta.cz',
            'first_name': 'Eva',
        })
        self.assertRedirects(response, reverse('nastaveni'))
        eva.refresh_from_db()
        self.assertEqual(eva.email, 'eva@posta.cz')
        self.assertEqual(eva.first_name, 'Eva')
        self.assertEqual(self.client.post(reverse('uzivatel_detail', args=[jiri.pk]), {
            'akce': 'ucet',
            'username': 'jiri2',
            'email': 'jiri@posta.cz',
            'first_name': 'Jiří',
        }).status_code, 403)
        jiri.refresh_from_db()
        self.assertEqual(jiri.username, 'jiri')


PNG = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
    b'\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'
    b'\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4'
    b'\x00\x00\x00\x00IEND\xaeB`\x82'
)


@override_settings(POSTAK_PREFIX='')
class FotoTests(TestCase):
    def test_fotografie_a_odmitnuti(self):
        eva = uzivatel('eva')
        jiri = uzivatel('jiri')
        self.client.force_login(eva)
        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(MEDIA_ROOT=tmp):
                spatne = self.client.post(reverse('nastaveni'), {
                    'akce': 'profil',
                    'email': 'eva@posta.cz',
                    'first_name': 'Eva',
                    'foto': SimpleUploadedFile('obrazek.png', b'<svg></svg>', content_type='image/png'),
                })
                self.assertEqual(spatne.status_code, 200)
                self.assertFalse(hasattr(eva, 'profil') and eva.profil.foto)

                velke = b'\x89PNG\r\n\x1a\n' + b'x' * (2 * 1024 * 1024)
                prilis = self.client.post(reverse('nastaveni'), {
                    'akce': 'profil',
                    'email': 'eva@posta.cz',
                    'first_name': 'Eva',
                    'foto': SimpleUploadedFile('velke.png', velke, content_type='image/png'),
                })
                self.assertEqual(prilis.status_code, 200)

                self.client.post(reverse('nastaveni'), {
                    'akce': 'profil',
                    'email': 'eva@posta.cz',
                    'first_name': 'Eva',
                    'foto': SimpleUploadedFile('ja.png', PNG, content_type='image/jpeg'),
                })
                eva.refresh_from_db()
                self.assertTrue(eva.profil.foto.name.endswith('.png'))
                foto = self.client.get(reverse('profil_foto', args=[eva.pk]))
                self.assertEqual(foto.status_code, 200)
                self.assertEqual(foto['Content-Type'], 'image/png')
                self.assertEqual(foto['X-Content-Type-Options'], 'nosniff')
                foto.close()

                self.client.force_login(jiri)
                self.assertEqual(self.client.get(reverse('profil_foto', args=[eva.pk])).status_code, 403)
                self.client.logout()
                self.assertEqual(self.client.get(reverse('profil_foto', args=[eva.pk])).status_code, 302)


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
