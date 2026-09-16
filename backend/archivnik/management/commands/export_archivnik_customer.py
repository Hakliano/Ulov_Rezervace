from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from archivnik.kartoteka_export import export_customer_zip
from salons.models import Salon


class Command(BaseCommand):
    help = (
        'Servisní export jedné kartotéky Archivníka do ZIP. '
        'Vyžaduje salon-id i customer-uuid. Nic nemaže.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--salon-id', type=int, required=True)
        parser.add_argument('--customer-uuid', required=True)
        parser.add_argument('--out', required=True, help='Cesta k výstupnímu ZIP.')

    def handle(self, *args, **options):
        salon = Salon.objects.filter(pk=options['salon_id']).first()
        if salon is None:
            raise CommandError(f'Salon {options["salon_id"]} neexistuje.')
        result = export_customer_zip(salon, options['customer_uuid'], Path(options['out']))
        self.stdout.write(self.style.SUCCESS(
            f'ZIP {result["path"]} customer={result["customer_uuid"]} soubory={result["files"]}'
        ))
