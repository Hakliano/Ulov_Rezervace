from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from salons.models import Salon

from .models import PartnerAdminProfil, PartnerNastaveni
from .permissions import ROLE_ADMIN_FINANCE, ROLE_KAM
from .tym import vytvor_tym_uzivatele


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class TymPristupyTests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.salon = Salon.objects.create(name='Test Salon', email='majitel@example.test')
        self.partner = self.salon.partner_nastaveni
        self.partner.fakturacni_email = 'platby@example.test'
        self.partner.variabilni_symbol = '9000000099'
        self.partner.castka = Decimal('499.00')
        self.partner.dalsi_splatnost = date(2026, 1, 31)
        self.partner.save()
        self.superuser = self.User.objects.create_superuser(
            username='superadmin',
            email='admin@example.test',
            password='bezpecne-test-heslo',
        )
        self.kam_user = self._tym('kam@example.test', 'KAM Tester', ROLE_KAM)
        self.finance_user = self._tym('finance@example.test', 'Finance Tester', ROLE_ADMIN_FINANCE)

    def _tym(self, email, jmeno, role):
        user = self.User.objects.create_user(
            username=email,
            email=email,
            password='tymove-heslo-10',
            first_name=jmeno,
            is_staff=True,
            is_superuser=False,
        )
        PartnerAdminProfil.objects.create(user=user, jmeno=jmeno, role=role)
        return user

    def test_kam_nemuze_post_platbu_ani_otevrit_vydaje(self):
        self.client.force_login(self.kam_user)
        response = self.client.post(
            reverse('partner_admin:potvrdit_platbu', args=[self.salon.id]),
            {
                'zaplaceno_dne': '2026-02-02',
                'prijata_castka': '499.00',
                'poznamka': 'KAM nesmí',
            },
        )
        self.assertEqual(response.status_code, 403)
        self.partner.refresh_from_db()
        self.assertEqual(self.partner.dalsi_splatnost, date(2026, 1, 31))
        self.assertEqual(self.client.get(reverse('partner_admin:vydaje')).status_code, 403)
        self.assertEqual(self.client.get(reverse('partner_admin:ucty')).status_code, 403)
        self.assertEqual(self.client.get(reverse('partner_admin:emaily')).status_code, 403)
        self.assertEqual(self.client.get(reverse('partner_admin:tym')).status_code, 403)

    def test_kam_admin_presmeruje_na_partner_admin(self):
        self.client.force_login(self.kam_user)
        for path in ('/admin/', '/admin/login/'):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response['Location'], '/partner-admin/')
        changelist = self.client.get('/admin/auth/user/')
        self.assertEqual(changelist.status_code, 302)
        self.assertEqual(changelist['Location'], '/partner-admin/')
        self.client.force_login(self.superuser)
        self.assertEqual(self.client.get('/admin/').status_code, 200)

    def test_kam_cest_prehled_a_novy_partner(self):
        self.client.force_login(self.kam_user)
        prehled = self.client.get(reverse('partner_admin:dashboard'))
        self.assertEqual(prehled.status_code, 200)
        self.assertContains(prehled, 'KAM')
        self.assertNotContains(prehled, 'Napsat e-mail')
        self.assertNotContains(prehled, 'Výdaje tento měsíc')
        self.assertEqual(self.client.get(reverse('partner_admin:novy')).status_code, 200)
        self.assertEqual(self.client.get(reverse('partner_admin:faktury')).status_code, 200)
        self.assertEqual(self.client.get(reverse('partner_admin:potencialni')).status_code, 200)

    def test_finance_nemuze_novy_partner_ani_admin(self):
        self.client.force_login(self.finance_user)
        self.assertEqual(self.client.get(reverse('partner_admin:novy')).status_code, 403)
        self.assertEqual(self.client.post(reverse('partner_admin:novy'), {'name': 'X'}).status_code, 403)
        admin_resp = self.client.get('/admin/')
        self.assertEqual(admin_resp.status_code, 302)
        self.assertEqual(admin_resp['Location'], '/partner-admin/')
        self.assertEqual(self.client.get(reverse('partner_admin:emaily')).status_code, 403)
        self.assertEqual(self.client.get(reverse('partner_admin:tym')).status_code, 403)
        blokace = self.client.post(
            reverse('partner_admin:blokovat', args=[self.salon.id]),
            {'potvrzeni': 'BLOCK', 'duvod': 'test'},
        )
        self.assertEqual(blokace.status_code, 403)
        self.partner.refresh_from_db()
        self.assertEqual(self.partner.stav, PartnerNastaveni.STAV_ACTIVE)

    def test_finance_muze_prehled_a_vydaje(self):
        self.client.force_login(self.finance_user)
        prehled = self.client.get(reverse('partner_admin:dashboard'))
        self.assertEqual(prehled.status_code, 200)
        self.assertContains(prehled, 'ADMIN/Finance')
        self.assertNotContains(prehled, '+ Nový partner')
        self.assertEqual(self.client.get(reverse('partner_admin:vydaje')).status_code, 200)
        self.assertEqual(self.client.get(reverse('partner_admin:ucty')).status_code, 200)
        self.assertEqual(self.client.get(reverse('partner_admin:testovaci_pristupy')).status_code, 200)

    def test_superuser_vytvori_uzivatele_a_zkusi_email(self):
        self.client.force_login(self.superuser)
        stranka = self.client.get(reverse('partner_admin:tym'))
        self.assertEqual(stranka.status_code, 200)
        self.assertContains(stranka, 'Tým ULOV')
        response = self.client.post(
            reverse('partner_admin:tym'),
            {
                'jmeno': 'Nová KAM',
                'email': 'nova.kam@example.test',
                'heslo': 'docasne-heslo-10',
                'role': ROLE_KAM,
            },
        )
        self.assertEqual(response.status_code, 302)
        user = self.User.objects.get(email='nova.kam@example.test')
        self.assertTrue(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(user.partner_admin_profil.role, ROLE_KAM)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('nova.kam@example.test', mail.outbox[0].body)
        self.assertIn('partner-admin', mail.outbox[0].body)
        self.assertTrue(mail.outbox[0].alternatives)

    def test_email_selze_ale_ucet_zustane(self):
        self.client.force_login(self.superuser)
        with patch('partner_admin.tym._odesli_pristup', side_effect=RuntimeError('SMTP down')):
            response = self.client.post(
                reverse('partner_admin:tym'),
                {
                    'jmeno': 'Finance bez mailu',
                    'email': 'finance.fail@example.test',
                    'heslo': 'docasne-heslo-10',
                    'role': ROLE_ADMIN_FINANCE,
                },
                follow=True,
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(self.User.objects.filter(email='finance.fail@example.test').exists())
        self.assertContains(response, 'e-mail se nepodařilo odeslat')

    def test_staff_bez_profilu_nejde_do_panelu(self):
        staff = self.User.objects.create_user(
            username='staff@example.test',
            email='staff@example.test',
            password='heslo-staff-10',
            is_staff=True,
        )
        self.client.force_login(staff)
        response = self.client.get(reverse('partner_admin:dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/partner-admin/login/', response['Location'])

    def test_vytvor_tym_uzivatele_helper(self):
        user, profil, email_ok, _chyba = vytvor_tym_uzivatele(
            jmeno='Helper',
            email='helper@example.test',
            heslo='helper-heslo-10',
            role=ROLE_ADMIN_FINANCE,
        )
        self.assertTrue(email_ok)
        self.assertTrue(user.check_password('helper-heslo-10'))
        self.assertEqual(profil.role, ROLE_ADMIN_FINANCE)
        self.assertEqual(len(mail.outbox), 1)


@override_settings(
    DEBUG=False,
    SENTRY_ENVIRONMENT='production',
    API_PUBLIC_BASE_URL='https://api.ulovklienty.cz/api',
)
class PartnerAdminLoginTests(TestCase):
    def test_branded_login_page_vraci_200_a_ulov_branding(self):
        response = self.client.get('/partner-admin/login/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'ULOV KLIENTY')
        self.assertContains(response, 'New%20Project.webp')
        self.assertNotContains(response, 'sidebar-env-staging')
        self.assertNotContains(response, 'sidebar-env-lokal')
        self.assertContains(response, 'csrfmiddlewaretoken')
        self.assertContains(response, 'E-mail nebo uživatelské jméno')
        self.assertContains(response, 'Heslo')
        self.assertNotContains(response, 'Django administration')

    def test_neuspesne_prihlaseni_neotevre_panel(self):
        response = self.client.post(
            '/partner-admin/login/',
            {'username': 'nikdo@example.test', 'password': 'spatne-heslo-99'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Neplatný e-mail, jméno nebo heslo.')
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_uspesne_prihlaseni_jde_do_panelu(self):
        User = get_user_model()
        User.objects.create_superuser(
            username='superadmin',
            email='admin@example.test',
            password='bezpecne-test-heslo',
        )
        response = self.client.post(
            '/partner-admin/login/',
            {'username': 'admin@example.test', 'password': 'bezpecne-test-heslo'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/partner-admin/')
        panel = self.client.get('/partner-admin/')
        self.assertEqual(panel.status_code, 200)

    def test_staff_bez_profilu_se_neprihlasi(self):
        User = get_user_model()
        User.objects.create_user(
            username='staff@example.test',
            email='staff@example.test',
            password='heslo-staff-10',
            is_staff=True,
        )
        response = self.client.post(
            '/partner-admin/login/',
            {'username': 'staff@example.test', 'password': 'heslo-staff-10'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'nemá přístup do partner-admin')
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_admin_login_presmeruje_na_branded(self):
        response = self.client.get('/admin/login/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/partner-admin/login/', response['Location'])


LOGO_ULOV = 'New%20Project.webp'


class PartnerAdminProstrediZnackaTests(TestCase):
    def test_staging_login_misto_loga(self):
        with override_settings(
            DEBUG=False,
            SENTRY_ENVIRONMENT='staging',
            API_PUBLIC_BASE_URL='https://api-staging.ulovklienty.cz/api',
        ):
            response = self.client.get('/partner-admin/login/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'sidebar-env-staging')
        self.assertContains(response, 'Staging')
        self.assertNotContains(response, LOGO_ULOV)

    def test_live_login_ma_logo(self):
        with override_settings(
            DEBUG=False,
            SENTRY_ENVIRONMENT='production',
            API_PUBLIC_BASE_URL='https://api.ulovklienty.cz/api',
        ):
            response = self.client.get('/partner-admin/login/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, LOGO_ULOV)
        self.assertNotContains(response, 'sidebar-env-staging')
        self.assertNotContains(response, 'sidebar-env-lokal')

    def test_lokal_login_misto_loga(self):
        with override_settings(DEBUG=True, SENTRY_ENVIRONMENT='production'):
            response = self.client.get('/partner-admin/login/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'sidebar-env-lokal')
        self.assertContains(response, 'Lokál')
        self.assertNotContains(response, LOGO_ULOV)

    def test_staging_panel_po_prihlaseni(self):
        User = get_user_model()
        user = User.objects.create_superuser(
            username='superadmin',
            email='admin@example.test',
            password='bezpecne-test-heslo',
        )
        self.client.force_login(user)
        with override_settings(
            DEBUG=False,
            SENTRY_ENVIRONMENT='staging',
            API_PUBLIC_BASE_URL='https://api-staging.ulovklienty.cz/api',
        ):
            response = self.client.get('/partner-admin/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'sidebar-env-staging')
        self.assertContains(response, 'Staging')
        self.assertNotContains(response, LOGO_ULOV)

