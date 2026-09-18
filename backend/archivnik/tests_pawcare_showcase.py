from io import StringIO

from django.core.management import call_command
from django.db.models import Count
from django.test import TestCase

from archivnik.models import Asset, Customer, Entry, Obor, Object, Reminder, ReminderStav
from archivnik.pawcare_showcase import EXPECTED_NAME, PawCareShowcaseError, seed_pawcare
from rezervace.models import Zamestnanec
from salons.models import CenikPolozka, Salon


def _pawcare(name=EXPECTED_NAME):
    salon = Salon.objects.create(name=name, email='info@pawcare.cz')
    owner = Zamestnanec.objects.create(
        salon=salon,
        jmeno='Majitelka',
        role=Zamestnanec.ROLE_MAJITEL,
        prihlasovaci_jmeno='info@pawcare.cz',
        aktivni=True,
        zobrazit_na_webu=False,
    )
    CenikPolozka.objects.create(salon=salon, nazev='Preventivní prohlídka', cena=650, delka_minut=30)
    return salon, owner


class SeedPawcareShowcaseTests(TestCase):
    def test_seed_naplni_existujici_pawcare_bez_assets(self):
        salon, owner = _pawcare()
        other = Salon.objects.create(name='Cizí salon', email='cizi@demo.local')
        keep = Customer.objects.create(salon=other, prijmeni='Cizí', email='cizi.zakaznik@demo.local')
        worker = Zamestnanec.objects.create(
            salon=salon, jmeno='MVDr Petr Veselý', role=Zamestnanec.ROLE_ZAMESTNANEC, aktivni=True,
        )

        call_command('seed_pawcare_showcase', salon_id=salon.id, stdout=StringIO())
        call_command('seed_pawcare_showcase', salon_id=salon.id, stdout=StringIO())

        salon.refresh_from_db()
        owner.refresh_from_db()
        self.assertEqual(salon.name, EXPECTED_NAME)
        self.assertEqual(salon.email, 'info@pawcare.cz')
        self.assertEqual(owner.jmeno, 'Majitelka')
        self.assertTrue(Zamestnanec.objects.filter(pk=worker.pk, jmeno='MVDr Petr Veselý').exists())
        self.assertEqual(CenikPolozka.objects.filter(salon=salon).count(), 1)
        self.assertTrue(Obor.objects.filter(salon=salon, zdroj_preset='vet').exists())
        self.assertEqual(Customer.objects.filter(salon=salon).count(), 15)
        self.assertGreaterEqual(Object.objects.filter(salon=salon).count(), 20)
        self.assertLessEqual(Object.objects.filter(salon=salon).count(), 25)
        self.assertGreaterEqual(Entry.objects.filter(salon=salon).count(), 40)
        self.assertLessEqual(Entry.objects.filter(salon=salon).count(), 60)
        aktivni = Reminder.objects.filter(salon=salon, stav=ReminderStav.AKTIVNI).count()
        self.assertGreaterEqual(aktivni, 8)
        self.assertLessEqual(aktivni, 12)
        self.assertTrue(Reminder.objects.filter(salon=salon, stav=ReminderStav.HOTOVO).exists())
        self.assertEqual(Asset.objects.filter(salon=salon).count(), 0)

        lucie = Customer.objects.get(salon=salon, jmeno='Lucie', prijmeni='Dvořáková')
        self.assertEqual(Object.objects.filter(zakaznik=lucie, nazev='Max').count(), 1)
        martin = Customer.objects.get(salon=salon, jmeno='Martin', prijmeni='Jelínek')
        self.assertEqual(
            set(Object.objects.filter(zakaznik=martin).values_list('nazev', flat=True)),
            {'Bella', 'Charlie'},
        )
        self.assertTrue(
            Customer.objects.filter(salon=salon).annotate(n=Count('objekty')).filter(n=1).exists()
        )
        self.assertTrue(
            Customer.objects.filter(salon=salon).annotate(n=Count('objekty')).filter(n__gte=3).exists()
        )
        self.assertTrue(Customer.objects.filter(pk=keep.pk).exists())

    def test_odmitne_cizi_salon(self):
        salon, _owner = _pawcare(name='Studio Krása')
        with self.assertRaises(PawCareShowcaseError):
            seed_pawcare(salon_id=salon.id)

    def test_bez_reset_nesmaze_rucni_zmenu(self):
        salon, _owner = _pawcare()
        seed_pawcare(salon_id=salon.id)
        extra = Customer.objects.create(
            salon=salon, jmeno='Ruční', prijmeni='Zákazník', email='rucni.zakaznik@demo.local',
        )
        before = Customer.objects.filter(salon=salon).count()
        seed_pawcare(salon_id=salon.id)
        self.assertTrue(Customer.objects.filter(pk=extra.pk).exists())
        self.assertEqual(Customer.objects.filter(salon=salon).count(), before)

    def test_reset_obnovi_jen_kartoteku_pawcare(self):
        salon, owner = _pawcare()
        worker = Zamestnanec.objects.create(
            salon=salon, jmeno='Tým PawCare', role=Zamestnanec.ROLE_ZAMESTNANEC, aktivni=True,
        )
        other = Salon.objects.create(name='Cizí B', email='cizi-b@demo.local')
        keep = Customer.objects.create(salon=other, prijmeni='Nechat', email='nechat@demo.local')
        seed_pawcare(salon_id=salon.id)
        Customer.objects.create(
            salon=salon, jmeno='Navíc', prijmeni='Karta', email='navic.karta@demo.local',
        )
        seed_pawcare(salon_id=salon.id, reset=True)
        salon.refresh_from_db()
        owner.refresh_from_db()
        self.assertFalse(Customer.objects.filter(salon=salon, email='navic.karta@demo.local').exists())
        self.assertEqual(Customer.objects.filter(salon=salon).count(), 15)
        self.assertTrue(Customer.objects.filter(pk=keep.pk).exists())
        self.assertEqual(Asset.objects.filter(salon=salon).count(), 0)
        self.assertEqual(salon.email, 'info@pawcare.cz')
        self.assertEqual(owner.jmeno, 'Majitelka')
        self.assertTrue(Zamestnanec.objects.filter(pk=worker.pk).exists())
        self.assertEqual(CenikPolozka.objects.filter(salon=salon, nazev='Preventivní prohlídka').count(), 1)
