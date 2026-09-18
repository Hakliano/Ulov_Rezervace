from django.core.management.base import BaseCommand, CommandError

from archivnik.models import Customer
from archivnik.p56a_fixtures import (
    DELETE_EMAIL,
    DELETE_NOTE,
    DELETE_PHONE,
    vytvor_plnou_kartoteku,
    zajisti_booking_se_stejnym_emailem,
)
from salons.models import Salon


class Command(BaseCommand):
    help = (
        'Vytvoří jednu testovací kartotéku P5.6A (delete target) včetně Bunny souboru '
        'a rezervace se stejným e-mailem. Nespouštět z deploye. Nic newipeuje.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--salon-id', type=int, required=True)

    def handle(self, *args, **options):
        salon = Salon.objects.filter(pk=options['salon_id']).first()
        if salon is None:
            raise CommandError(f'Salon {options["salon_id"]} neexistuje.')
        existing = Customer.objects.filter(salon=salon, email=DELETE_EMAIL).first()
        if existing:
            self.stdout.write(f'už existuje uuid={existing.uuid} email={DELETE_EMAIL}')
            zak, rez = zajisti_booking_se_stejnym_emailem(salon, DELETE_EMAIL)
            self.stdout.write(f'booking zakaznik_id={zak.id} rezervace_id={rez.id}')
            return
        created = vytvor_plnou_kartoteku(
            salon,
            email=DELETE_EMAIL,
            telefon=DELETE_PHONE,
            poznamka=DELETE_NOTE,
        )
        zak, rez = zajisti_booking_se_stejnym_emailem(salon, DELETE_EMAIL)
        customer = created['customer']
        self.stdout.write(self.style.SUCCESS(
            f'created uuid={customer.uuid} email={customer.email} '
            f'asset={created["asset"].uuid} booking={zak.id}/{rez.id}'
        ))
