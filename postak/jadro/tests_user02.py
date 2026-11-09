from unittest.mock import patch

from django.contrib.auth.models import User
from django.template.loader import render_to_string
from django.test import TestCase, override_settings
from django.urls import reverse

from jadro.mail_send import MailError
from jadro.models import EmailSchranka, Profil
from jadro.user_credentials import logo_url_pro_email, odeslat_prihlasovaci_udaje, prihlasovaci_email_uzivatele
from jadro.user_credentials_models import OdeslaniPrihlasovacich

HESLO = 'Spravne-heslo-1'
LOGIN_URL = 'https://www.ulovklienty.cz/postak/'


def uzivatel(username, *, superuser=False, password=HESLO, email=''):
    user = User.objects.create_user(username, password=password, email=email)
    if superuser:
        user.is_superuser = True
        user.save(update_fields=['is_superuser'])
    return user


def schranka_ok():
    return EmailSchranka.objects.create(
        email='system@example.test',
        projekt=EmailSchranka.PROJEKT_MODERNIK,
        prihlasovaci_jmeno='system@example.test',
        test_stav=EmailSchranka.STAV_OK,
    )


@override_settings(
    POSTAK_PREFIX='',
    POSTAK_PUBLIC_LOGIN_URL=LOGIN_URL,
    POSTAK_LOGO_URL='https://example.test/logo.webp',
)
class User02Tests(TestCase):
    def setUp(self):
        self.admin = uzivatel('admin', superuser=True)
        self.eva = uzivatel('eva', email='eva@firma.cz')
        self.box = schranka_ok()

    def test_email_logo_je_png(self):
        url = logo_url_pro_email()
        self.assertIn('postak-logo-email.png', url)
        self.assertNotIn('.webp', url.lower())

    def test_prihlasovaci_email_z_uctu(self):
        self.assertEqual(prihlasovaci_email_uzivatele(self.eva), 'eva@firma.cz')
        bez = uzivatel('jen_jmeno')
        self.assertEqual(prihlasovaci_email_uzivatele(bez), 'jen_jmeno')

    def test_sablony_obsahuji_login_a_odkaz(self):
        html = render_to_string(
            'email/prihlasovaci_udaje.html',
            {
                'uzivatel': self.eva,
                'login_id': 'eva@firma.cz',
                'heslo': 'Docasne-123',
                'login_url': LOGIN_URL,
                'logo_url': 'https://example.test/logo.png',
            },
        )
        text = render_to_string(
            'email/prihlasovaci_udaje.txt',
            {
                'login_id': 'eva@firma.cz',
                'heslo': 'Docasne-123',
                'login_url': LOGIN_URL,
            },
        )
        self.assertIn('Vítejte v Pošťákovi!', html)
        self.assertIn('eva@firma.cz', html)
        self.assertIn('Přihlásit se do Pošťáka', html)
        self.assertIn(LOGIN_URL, html)
        self.assertIn(LOGIN_URL, text)
        self.assertIn('eva@firma.cz', text)

    @patch('jadro.user_credentials.send_system_message')
    def test_odeslani_zmeni_heslo_az_po_uspechu(self, send_mock):
        send_mock.return_value = 'msg-id'
        old_hash = self.eva.password
        z = odeslat_prihlasovaci_udaje(
            cil=self.eva,
            odeslal=self.admin,
            prijemce='jinak@domena.cz',
        )
        self.assertTrue(z.uspech)
        self.eva.refresh_from_db()
        self.assertNotEqual(self.eva.password, old_hash)
        profil = Profil.objects.get(user=self.eva)
        self.assertTrue(profil.vyzadovat_zmenu_hesla)
        args, kwargs = send_mock.call_args
        self.assertEqual(kwargs['to'], 'jinak@domena.cz')
        self.assertIn('eva@firma.cz', kwargs['html_body'])
        self.assertIn(LOGIN_URL, kwargs['html_body'])
        self.assertFalse(OdeslaniPrihlasovacich.objects.filter(pk=z.pk).first().chyba)

    @patch('jadro.user_credentials.send_system_message', side_effect=MailError('SMTP pad'))
    def test_selhani_nezmeni_heslo(self, _send):
        old_hash = self.eva.password
        z = odeslat_prihlasovaci_udaje(
            cil=self.eva,
            odeslal=self.admin,
            prijemce='x@y.cz',
        )
        self.assertFalse(z.uspech)
        self.eva.refresh_from_db()
        self.assertEqual(self.eva.password, old_hash)
        self.assertFalse(Profil.objects.filter(user=self.eva, vyzadovat_zmenu_hesla=True).exists())

    def test_opravneni_superuser(self):
        self.client.force_login(self.eva)
        url = reverse('uzivatel_odeslat_prihlasovaci', args=[self.eva.pk])
        self.assertEqual(self.client.get(url).status_code, 403)

    @patch('jadro.views.odeslat_prihlasovaci_udaje')
    def test_formular_odeslani(self, odeslat_mock):
        class Z:
            uspech = True
            prijemce = 'kontakt@jiny.cz'

        odeslat_mock.return_value = Z()
        self.client.force_login(self.admin)
        url = reverse('uzivatel_odeslat_prihlasovaci', args=[self.eva.pk])
        detail = reverse('uzivatel_detail', args=[self.eva.pk])
        response = self.client.post(url, {
            'prijemce': 'kontakt@jiny.cz',
            'potvrzeni': 'on',
            'akce': 'odeslat',
        })
        self.assertRedirects(response, detail)
        odeslat_mock.assert_called_once()
        _, kwargs = odeslat_mock.call_args
        self.assertEqual(kwargs['prijemce'], 'kontakt@jiny.cz')

    def test_detail_ma_tlacitko(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('uzivatel_detail', args=[self.eva.pk]))
        self.assertContains(response, 'Odeslat přihlašovací údaje')
        self.assertContains(response, 'eva@firma.cz')

    def test_middleware_vynuti_nastaveni(self):
        profil, _ = Profil.objects.get_or_create(user=self.eva)
        profil.vyzadovat_zmenu_hesla = True
        profil.save()
        self.client.force_login(self.eva)
        response = self.client.get(reverse('prehled'))
        self.assertRedirects(response, reverse('nastaveni'))

    def test_zmena_hesla_zrusi_flag(self):
        profil, _ = Profil.objects.get_or_create(user=self.eva)
        profil.vyzadovat_zmenu_hesla = True
        profil.save()
        self.client.force_login(self.eva)
        nove = 'Nove-heslo-33'
        response = self.client.post(reverse('nastaveni'), {
            'akce': 'heslo',
            'old_password': HESLO,
            'new_password1': nove,
            'new_password2': nove,
        })
        self.assertRedirects(response, reverse('nastaveni'))
        profil.refresh_from_db()
        self.assertFalse(profil.vyzadovat_zmenu_hesla)
