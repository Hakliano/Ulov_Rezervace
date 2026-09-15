from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from archivnik.models import ArchivnikSession, CustomFieldDef, FieldKind, Obor, ObjectType
from partner_admin.models import MODUL_ARCHIVNIK, PartnerModul
from partner_admin.services import resetuj_heslo_majitele
from partner_admin.services_moduly import nastav_modul
from rezervace.models import Zamestnanec
from salons.models import Salon


class Actor:
    username = 'p42-test'


def _salon(name, email):
    salon = Salon.objects.create(name=name, email=email)
    owner = Zamestnanec.objects.create(
        salon=salon,
        jmeno=f'Majitel {name}',
        role=Zamestnanec.ROLE_MAJITEL,
        prihlasovaci_jmeno=email,
        aktivni=True,
    )
    owner.set_password('archivnik123')
    owner.save(update_fields=['password_hash'])
    return salon, owner


class ArchivnikSpravaTests(TestCase):
    def setUp(self):
        self.superuser = get_user_model().objects.create_superuser(
            username='superadmin',
            email='admin@example.test',
            password='bezpecne-test-heslo',
        )
        self.salon_a, self.owner_a = _salon('Tenant A', 'a@archivnik.test')
        self.salon_b, self.owner_b = _salon('Tenant B', 'b@archivnik.test')
        nastav_modul(self.salon_a, MODUL_ARCHIVNIK, True, Actor())
        nastav_modul(self.salon_b, MODUL_ARCHIVNIK, True, Actor())

        self.obor_a = Obor.objects.create(
            salon=self.salon_a, nazev='Veterina', poradi=1,
            zdroj_preset='vet', objekt_jednotne='Zvíře', objekt_mnozne='Zvířata',
        )
        self.historicky_a = Obor.objects.create(
            salon=self.salon_a, nazev='Pneuservis', poradi=2,
            zdroj_preset='pneu', objekt_jednotne='Vozidlo', objekt_mnozne='Vozidla',
        )
        pes = ObjectType.objects.create(
            salon=self.salon_a, obor=self.obor_a, nazev='Pes', zdroj_preset='vet', aktivni=True,
        )
        CustomFieldDef.objects.create(
            salon=self.salon_a, typ=pes, nazev='Plemeno', druh=FieldKind.TEXT,
            zdroj_preset='vet', aktivni=True,
        )
        CustomFieldDef.objects.create(
            salon=self.salon_a, typ=pes, nazev='Pohlaví', druh=FieldKind.VYBER,
            volby=['Fena', 'Pes'], zdroj_preset='vet', aktivni=False,
        )
        ObjectType.objects.create(
            salon=self.salon_a, obor=self.historicky_a, nazev='Osobní', zdroj_preset='pneu', aktivni=True,
        )
        ObjectType.objects.create(
            salon=self.salon_a, nazev='Starý typ', aktivni=False,
        )
        ObjectType.objects.create(
            salon=self.salon_b, nazev='Vozidlo B', aktivni=True,
        )
        self.staff_a = Zamestnanec.objects.create(
            salon=self.salon_a,
            jmeno='Sestra',
            role=Zamestnanec.ROLE_ZAMESTNANEC,
            prihlasovaci_jmeno='sestra@archivnik.test',
            aktivni=True,
        )
        self.staff_a.set_password('sestra12345')
        self.staff_a.save(update_fields=['password_hash'])

    def test_detail_ukazuje_odkaz_jen_kdyz_je_active(self):
        self.client.force_login(self.superuser)
        on = self.client.get(reverse('partner_admin:detail', args=[self.salon_a.id]))
        self.assertContains(on, 'Konfigurace Archivníka')
        PartnerModul.objects.filter(salon=self.salon_a, modul__kod=MODUL_ARCHIVNIK).update(
            status=PartnerModul.STAV_INACTIVE,
        )
        off = self.client.get(reverse('partner_admin:detail', args=[self.salon_a.id]))
        self.assertNotContains(off, 'Konfigurace Archivníka')

    def test_sprava_read_only_ukazuje_aktualni_historicke_a_bez_oboru(self):
        self.client.force_login(self.superuser)
        res = self.client.get(reverse('partner_admin:archivnik_sprava', args=[self.salon_a.id]))
        self.assertEqual(res.status_code, 200)
        html = res.content.decode()
        self.assertIn('Aktuální', html)
        self.assertIn('Historický', html)
        self.assertIn('Zvíře', html)
        self.assertIn('Zvířata', html)
        self.assertIn('Pes', html)
        self.assertIn('Plemeno', html)
        self.assertIn('Pohlaví', html)
        self.assertIn('Výběr', html)
        self.assertIn('Fena', html)
        self.assertIn('inactive', html)
        self.assertIn('Osobní', html)
        self.assertIn('Starý typ', html)
        self.assertIn('Bez oboru', html)
        self.assertIn('2 polí', html)
        self.assertIn('<details class="archivnik-typ-skupina" open>', html)
        self.assertNotIn('<details class="archivnik-typ" open', html)
        self.assertIn('Sestra', html)
        self.assertIn('sestra@archivnik.test', html)
        self.assertNotIn('password_hash', html)
        self.assertNotIn('archivnik123', html)
        self.assertNotContains(res, 'Zapnout Archivník')
        self.assertNotContains(res, 'apply_preset')
        self.assertNotIn('Vozidlo B', html)

    def test_vypnuty_modul_stale_ukaze_data_s_bannerem(self):
        PartnerModul.objects.filter(salon=self.salon_a, modul__kod=MODUL_ARCHIVNIK).update(
            status=PartnerModul.STAV_INACTIVE,
        )
        self.client.force_login(self.superuser)
        res = self.client.get(reverse('partner_admin:archivnik_sprava', args=[self.salon_a.id]))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Archivník je vypnutý')
        self.assertContains(res, 'Pes')
        self.assertContains(res, 'Starý typ')

    def test_tenant_isolation_a_jen_superadmin(self):
        res = self.client.get(reverse('partner_admin:archivnik_sprava', args=[self.salon_a.id]))
        self.assertEqual(res.status_code, 302)

        normal = get_user_model().objects.create_user(username='ops', password='heslo-12345')
        self.client.force_login(normal)
        forbidden = self.client.get(reverse('partner_admin:archivnik_sprava', args=[self.salon_a.id]))
        self.assertEqual(forbidden.status_code, 302)

        self.client.force_login(self.superuser)
        a = self.client.get(reverse('partner_admin:archivnik_sprava', args=[self.salon_a.id]))
        b = self.client.get(reverse('partner_admin:archivnik_sprava', args=[self.salon_b.id]))
        self.assertContains(a, 'Pes')
        self.assertNotContains(a, 'Vozidlo B')
        self.assertContains(b, 'Vozidlo B')
        self.assertNotContains(b, 'Pes')
        self.assertNotContains(b, 'a@archivnik.test')

    def test_reset_hesla_zrusi_jen_archivnik_session_majitele(self):
        expirace = timezone.now() + timedelta(days=10)
        ArchivnikSession.objects.create(zamestnanec=self.owner_a, expirace=expirace)
        ArchivnikSession.objects.create(zamestnanec=self.staff_a, expirace=expirace)
        ArchivnikSession.objects.create(zamestnanec=self.owner_b, expirace=expirace)

        resetuj_heslo_majitele(self.owner_a, 'nove-bezpecne-heslo', Actor())
        self.assertFalse(self.owner_a.archivnik_sessiony.exists())
        self.assertTrue(self.staff_a.archivnik_sessiony.exists())
        self.assertTrue(self.owner_b.archivnik_sessiony.exists())
        self.owner_a.refresh_from_db()
        self.assertTrue(self.owner_a.check_password('nove-bezpecne-heslo'))
