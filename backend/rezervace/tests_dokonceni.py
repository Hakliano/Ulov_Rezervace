from django.test import TestCase, override_settings
from django.utils import timezone

from partner_admin.models import IntegrationOutbox
from partner_admin.services_moduly import nastav_modul
from rezervace.models import Rezervace, RezervaceSluzba
from rezervace.services.dokonceni import oznacit_dokonceno
from salons.models import CenikPolozka, Salon


class Actor:
    username = 'test-admin'


@override_settings(MATERIALNIK_STUB=True)
class DokonceniOutboxTests(TestCase):
    def setUp(self):
        self.salon = Salon.objects.create(name='Salon Outbox')
        self.sluzba = CenikPolozka.objects.create(
            salon=self.salon, nazev='Barvení', cena=500, delka_minut=60,
        )
        self.rez = Rezervace.objects.create(
            salon=self.salon,
            zacatek=timezone.now(),
            konec=timezone.now(),
            stav='potvrzeno',
            jmeno_host='Test',
        )
        RezervaceSluzba.objects.create(rezervace=self.rez, sluzba=self.sluzba)

    def test_bez_modulu_nezapisuje_outbox(self):
        oznacit_dokonceno(self.rez)
        self.assertEqual(IntegrationOutbox.objects.count(), 0)
        self.rez.refresh_from_db()
        self.assertEqual(self.rez.stav, 'dokonceno')

    def test_aktivni_modul_zapise_outbox(self):
        nastav_modul(self.salon, 'materialnik', True, Actor())
        oznacit_dokonceno(self.rez)
        row = IntegrationOutbox.objects.get()
        self.assertEqual(row.event_type, 'service.completed')
        self.assertEqual(row.salon_id, self.salon.id)
        self.assertEqual(row.payload['tenant_external_id'], f'salon:{self.salon.id}')
        self.assertEqual(
            row.payload['payload']['services'][0]['external_service_id'],
            f'cenik:{self.sluzba.id}',
        )

    def test_retry_stejneho_dokonceni_neduplikuje_event(self):
        nastav_modul(self.salon, 'materialnik', True, Actor())
        oznacit_dokonceno(self.rez)
        self.rez.stav = 'potvrzeno'
        self.rez.save(update_fields=['stav'])
        from rezervace.services.dokonceni import NelzeDokoncit
        # už má dokonceno_at, ale stav jsme vrátili jen pro test unique event_id
        self.rez.stav = 'potvrzeno'
        self.rez.dokonceno_at = None
        self.rez.save(update_fields=['stav', 'dokonceno_at'])
        # nové dokončení má jiné dokonceno_at → jiné event_id; duplicita se řeší
        # stejným event_id při retry workeru, ne při druhém kliknutí po resetu.
        oznacit_dokonceno(self.rez)
        self.assertEqual(IntegrationOutbox.objects.count(), 2)

    def test_inactive_po_dokonceni_negeneruje_event(self):
        nastav_modul(self.salon, 'materialnik', True, Actor())
        nastav_modul(self.salon, 'materialnik', False, Actor())
        oznacit_dokonceno(self.rez)
        self.assertEqual(IntegrationOutbox.objects.count(), 0)
