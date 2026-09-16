from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from archivnik.models import (
    ArchivnikSession,
    CustomFieldDef,
    CustomFieldValue,
    Customer,
    FieldKind,
    Obor,
    Object,
    ObjectType,
)
from archivnik.services import primary_obor
from partner_admin.models import MODUL_ARCHIVNIK, PartnerModul
from partner_admin.services import resetuj_heslo_majitele
from partner_admin.services_moduly import nastav_modul
from rezervace.models import SalonAuditLog, Zamestnanec
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


class ArchivnikFixture(TestCase):
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
            aktualni=True,
        )
        self.historicky_a = Obor.objects.create(
            salon=self.salon_a, nazev='Pneuservis', poradi=2,
            zdroj_preset='pneu', objekt_jednotne='Vozidlo', objekt_mnozne='Vozidla',
        )
        self.pes = ObjectType.objects.create(
            salon=self.salon_a, obor=self.obor_a, nazev='Pes', zdroj_preset='vet', aktivni=True,
        )
        CustomFieldDef.objects.create(
            salon=self.salon_a, typ=self.pes, nazev='Plemeno', druh=FieldKind.TEXT,
            zdroj_preset='vet', aktivni=True,
        )
        CustomFieldDef.objects.create(
            salon=self.salon_a, typ=self.pes, nazev='Pohlaví', druh=FieldKind.VYBER,
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


class ArchivnikSpravaTests(ArchivnikFixture):
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
        self.assertRegex(html, r'<details class="archivnik-typ-skupina"[^>]* open')
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


class ArchivnikSpravaWriteTests(ArchivnikFixture):
    def setUp(self):
        super().setUp()
        self.url = reverse('partner_admin:archivnik_sprava', args=[self.salon_a.id])
        self.liceni = Obor.objects.create(
            salon=self.salon_a, nazev='Líčení', poradi=3, aktualni=False,
        )
        self.pohlavi = CustomFieldDef.objects.get(typ=self.pes, nazev='Pohlaví')
        self.plemeno = CustomFieldDef.objects.get(typ=self.pes, nazev='Plemeno')
        self.client.force_login(self.superuser)

    def _post(self, **data):
        return self.client.post(self.url, data, follow=True)

    def test_primary_obor_preferuje_aktualni_ne_poradi(self):
        self.historicky_a.poradi = 0
        self.historicky_a.save(update_fields=['poradi', 'upraveno'])
        self.assertEqual(primary_obor(self.salon_a).id, self.obor_a.id)

    def test_nelze_dva_aktualni_obory(self):
        from django.db import transaction
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Obor.objects.filter(pk=self.historicky_a.pk).update(aktualni=True)

    def test_nastavit_aktualni_a_terminologii(self):
        res = self._post(akce='obor_aktualni', obor_id=str(self.historicky_a.id))
        self.assertEqual(res.status_code, 200)
        self.historicky_a.refresh_from_db()
        self.obor_a.refresh_from_db()
        self.assertTrue(self.historicky_a.aktualni)
        self.assertFalse(self.obor_a.aktualni)
        self.assertEqual(primary_obor(self.salon_a).id, self.historicky_a.id)
        self._post(
            akce='obor_ulozit',
            obor_id=str(self.historicky_a.id),
            nazev='Pneuservis',
            objekt_jednotne='Auto',
            objekt_mnozne='Auta',
        )
        self.historicky_a.refresh_from_db()
        self.assertEqual(self.historicky_a.objekt_jednotne, 'Auto')
        self.assertTrue(
            SalonAuditLog.objects.filter(
                salon=self.salon_a, objekt_typ='archivnik.Obor',
            ).exists()
        )

    def test_smazat_prazdny_obor_i_s_typy_bez_objektu(self):
        self._post(akce='obor_smazat', obor_id=str(self.liceni.id), potvrdit='1')
        self.assertFalse(Obor.objects.filter(pk=self.liceni.pk).exists())

        blocked_current = self._post(
            akce='obor_smazat', obor_id=str(self.obor_a.id), potvrdit='1',
        )
        self.assertContains(blocked_current, 'Nelze smazat aktuální Obor')
        self.assertTrue(Obor.objects.filter(pk=self.obor_a.pk).exists())

        self._post(akce='obor_smazat', obor_id=str(self.historicky_a.id), potvrdit='1')
        self.assertFalse(Obor.objects.filter(pk=self.historicky_a.pk).exists())
        self.assertFalse(ObjectType.objects.filter(salon=self.salon_a, nazev='Osobní').exists())
        self.assertFalse(ObjectType.objects.filter(salon=self.salon_a, obor__isnull=True, nazev='Osobní').exists())

    def test_typ_a_pole_hard_delete_jen_bez_dat(self):
        zak = Customer.objects.create(salon=self.salon_a, prijmeni='Novák')
        obj = Object(
            salon=self.salon_a, zakaznik=zak, typ=self.pes, nazev='Max',
        )
        obj.save()
        CustomFieldValue.objects.create(objekt=obj, pole=self.plemeno, hodnota='Labrador')

        blocked_typ = self._post(akce='typ_smazat', typ_id=str(self.pes.id), potvrdit='1')
        self.assertContains(blocked_typ, 'Nelze smazat typ Pes')
        self.assertTrue(ObjectType.objects.filter(pk=self.pes.pk).exists())
        self.assertTrue(Object.objects.filter(pk=obj.pk).exists())

        blocked_pole = self._post(akce='pole_smazat', pole_id=str(self.plemeno.id), potvrdit='1')
        self.assertContains(blocked_pole, 'Nelze smazat pole Plemeno')
        self.assertTrue(CustomFieldDef.objects.filter(pk=self.plemeno.pk).exists())
        self.assertEqual(
            CustomFieldValue.objects.get(objekt=obj, pole=self.plemeno).hodnota,
            'Labrador',
        )

        blocked_druh = self._post(
            akce='pole_ulozit',
            pole_id=str(self.plemeno.id),
            nazev='Plemeno',
            druh=FieldKind.CISLO,
            volby='',
            poradi='1',
            aktivni='1',
        )
        self.assertContains(blocked_druh, 'Nelze změnit druh pole Plemeno')

        self._post(
            akce='pole_ulozit',
            pole_id=str(self.pohlavi.id),
            nazev='Pohlaví',
            druh=FieldKind.VYBER,
            volby='Fena\nPes\nNeuvedeno',
            poradi='2',
        )
        self.pohlavi.refresh_from_db()
        self.assertIn('Neuvedeno', self.pohlavi.volby)

        CustomFieldValue.objects.create(objekt=obj, pole=self.pohlavi, hodnota='Pes')
        blocked_volba = self._post(
            akce='pole_ulozit',
            pole_id=str(self.pohlavi.id),
            nazev='Pohlaví',
            druh=FieldKind.VYBER,
            volby='Fena\nNeuvedeno',
            poradi='2',
        )
        self.assertContains(blocked_volba, 'Nelze odebrat volbu Pes')

        kocka = ObjectType.objects.create(
            salon=self.salon_a, obor=self.obor_a, nazev='Kočka', aktivni=True,
        )
        prazdne = CustomFieldDef.objects.create(
            salon=self.salon_a, typ=kocka, nazev='Barva', druh=FieldKind.TEXT, aktivni=True,
        )
        self._post(akce='pole_smazat', pole_id=str(prazdne.id), potvrdit='1')
        self.assertFalse(CustomFieldDef.objects.filter(pk=prazdne.pk).exists())
        self._post(akce='typ_smazat', typ_id=str(kocka.id), potvrdit='1')
        self.assertFalse(ObjectType.objects.filter(pk=kocka.pk).exists())
        obj.refresh_from_db()
        self.assertEqual(obj.nazev, 'Max')
        self.assertEqual(CustomFieldValue.objects.get(objekt=obj, pole=self.plemeno).hodnota, 'Labrador')

    def test_vytvoreni_oboru_typu_pole_a_deaktivace(self):
        self._post(
            akce='obor_vytvorit',
            nazev='Ordinace 2',
            objekt_jednotne='Pacient',
            objekt_mnozne='Pacienti',
        )
        novy = Obor.objects.get(salon=self.salon_a, nazev='Ordinace 2')
        self.assertFalse(novy.aktualni)
        self._post(
            akce='typ_vytvorit',
            obor_id=str(novy.id),
            nazev='Pták',
            poradi='1',
            aktivni='1',
            vyzaduje_nazev='1',
        )
        ptak = ObjectType.objects.get(salon=self.salon_a, nazev='Pták')
        self.assertEqual(ptak.obor_id, novy.id)
        self._post(
            akce='pole_vytvorit',
            typ_id=str(ptak.id),
            nazev='Kroužek',
            druh=FieldKind.TEXT,
            poradi='1',
            aktivni='1',
        )
        self.assertTrue(CustomFieldDef.objects.filter(typ=ptak, nazev='Kroužek').exists())
        self._post(akce='typ_aktivni', typ_id=str(ptak.id))
        ptak.refresh_from_db()
        self.assertFalse(ptak.aktivni)
        self._post(
            akce='typ_ulozit',
            typ_id=str(ptak.id),
            nazev='Pták',
            obor_id=str(self.obor_a.id),
            poradi='9',
            aktivni='1',
            vyzaduje_nazev='1',
        )
        ptak.refresh_from_db()
        self.assertEqual(ptak.obor_id, self.obor_a.id)
        self.assertTrue(ptak.aktivni)

    def test_tenant_isolation_write_a_jen_superadmin(self):
        cizi = ObjectType.objects.get(salon=self.salon_b, nazev='Vozidlo B')
        res = self._post(akce='typ_smazat', typ_id=str(cizi.id), potvrdit='1')
        self.assertContains(res, 'Typ v této provozovně neexistuje.')
        self.assertTrue(ObjectType.objects.filter(pk=cizi.pk).exists())

        self.client.logout()
        anon = self.client.post(self.url, {'akce': 'obor_vytvorit', 'nazev': 'Hack'})
        self.assertEqual(anon.status_code, 302)
        self.assertFalse(Obor.objects.filter(salon=self.salon_a, nazev='Hack').exists())

        normal = get_user_model().objects.create_user(username='ops2', password='heslo-12345')
        self.client.force_login(normal)
        forbidden = self.client.post(self.url, {'akce': 'obor_vytvorit', 'nazev': 'Hack'})
        self.assertEqual(forbidden.status_code, 302)
        self.assertFalse(Obor.objects.filter(salon=self.salon_a, nazev='Hack').exists())

