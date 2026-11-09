from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from jadro.chat_models import ChatZprava
from jadro.chat_services import konverzace, pocet_neprectenych

HESLO = 'Spravne-heslo-1'


def user(name, **kw):
    u = User.objects.create_user(name, password=HESLO, **kw)
    return u


class ChatTests(TestCase):
    def setUp(self):
        self.a = user('anna', first_name='Anna')
        self.b = user('boh', first_name='Boh')
        self.c = user('cyril', first_name='Cyril')

    def test_zprava_a_precteni(self):
        ChatZprava.objects.create(odesilatel=self.b, prijemce=self.a, text='Ahoj', precteno=False)
        self.assertEqual(pocet_neprectenych(self.a), 1)
        self.client.force_login(self.a)
        self.client.get(reverse('tym_konverzace', args=[self.b.pk]))
        self.assertEqual(pocet_neprectenych(self.a), 0)

    def test_treti_nevidi_konverzaci(self):
        ChatZprava.objects.create(odesilatel=self.a, prijemce=self.b, text='Tajné', precteno=False)
        self.client.force_login(self.c)
        html = self.client.get(reverse('tym_konverzace', args=[self.b.pk])).content.decode()
        self.assertNotIn('Tajné', html)
        self.assertEqual(konverzace(self.c, self.b).count(), 0)

    def test_odeslani_a_sync(self):
        self.client.force_login(self.a)
        response = self.client.post(reverse('tym_konverzace', args=[self.b.pk]), {'text': 'Ping'})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ChatZprava.objects.filter(odesilatel=self.a, text='Ping').exists())
        self.client.post(reverse('tym_sync', args=[self.b.pk]))

    def test_deaktivovany_neprijme(self):
        self.b.is_active = False
        self.b.save()
        self.client.force_login(self.a)
        response = self.client.post(reverse('tym_konverzace', args=[self.b.pk]), {'text': 'Ne'})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(ChatZprava.objects.filter(odesilatel=self.a, prijemce=self.b).exists())

    def test_escapovani_html(self):
        self.client.force_login(self.a)
        self.client.post(reverse('tym_konverzace', args=[self.b.pk]), {'text': '<script>x</script>'})
        self.client.force_login(self.b)
        html = self.client.get(reverse('tym_konverzace', args=[self.a.pk])).content.decode()
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)

    def test_prehled_chat_karta(self):
        ChatZprava.objects.create(odesilatel=self.b, prijemce=self.a, text='Novinka', precteno=False)
        self.client.force_login(self.a)
        response = self.client.get(reverse('prehled'))
        self.assertContains(response, 'Interní chat')
        self.assertContains(response, 'Novinka')

    def test_menu_badge(self):
        ChatZprava.objects.create(odesilatel=self.b, prijemce=self.a, text='x', precteno=False)
        self.client.force_login(self.a)
        response = self.client.get(reverse('prehled'))
        self.assertContains(response, 'nav-badge')

class PrehledEmailTests(TestCase):
    def test_imap_chyba_nezabije_prehled(self):
        from unittest.mock import patch

        from jadro.models import EmailSchranka

        admin = User.objects.create_superuser('su', password=HESLO)
        sch = EmailSchranka.objects.create(
            email='box@test.cz',
            projekt=EmailSchranka.PROJEKT_MODERNIK,
            prihlasovaci_jmeno='box@test.cz',
            imap_host='imap.test',
            imap_port=993,
            imap_ssl=True,
            smtp_host='smtp.test',
            smtp_port=465,
            smtp_ssl=True,
            heslo_sifra='',
        )
        sch.uzivatele.add(admin)
        self.client.force_login(admin)
        with patch('jadro.mail_prehled.overview_unseen', side_effect=Exception('timeout')):
            response = self.client.get(reverse('prehled'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'nejsou dostupné')
        self.assertNotContains(response, '3 000')
