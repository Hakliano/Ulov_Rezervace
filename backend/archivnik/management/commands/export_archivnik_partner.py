from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from archivnik.kartoteka_export import export_partner_zip
from salons.models import Salon


class Command(BaseCommand):
    help = (
        'Servisní exit export celého Archivníka jedné provozovny do ZIP. '
        'Tenant-scoped. Nic nemaže.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--salon-id', type=int, required=True)
        parser.add_argument('--out', required=True, help='Cesta k výstupnímu ZIP.')

    def handle(self, *args, **options):
        salon = Salon.objects.filter(pk=options['salon_id']).first()
        if salon is None:
            raise CommandError(f'Salon {options["salon_id"]} neexistuje.')
        result = export_partner_zip(salon, Path(options['out']))
        self.stdout.write(self.style.SUCCESS(
            f'ZIP {result["path"]} zakaznici={result["customers"]} soubory={result["files"]}'
        ))
