from django.core.management.base import BaseCommand, CommandError

from partner_admin.models import MODUL_ARCHIVNIK
from partner_admin.services_moduly import nastav_modul
from salons.models import Salon


class Command(BaseCommand):
    help = 'Zapne nebo vypne Archivník u salonu (lokální modul, bez FLOW).'

    def add_arguments(self, parser):
        parser.add_argument('--salon', type=int, required=True)
        parser.add_argument('--off', action='store_true')

    def handle(self, *args, **options):
        salon = Salon.objects.filter(pk=options['salon']).first()
        if not salon:
            raise CommandError(f'Salon {options["salon"]} neexistuje.')

        class Actor:
            username = 'staging-seed'

        row = nastav_modul(salon, MODUL_ARCHIVNIK, not options['off'], Actor())
        self.stdout.write(
            f'status={row.status} err={row.provisioning_error or "-"}'
        )
