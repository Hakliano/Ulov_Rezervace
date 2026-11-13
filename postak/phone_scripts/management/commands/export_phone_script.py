from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from phone_scripts.models import PhoneScript
from phone_scripts.services.import_export import export_script_json


class Command(BaseCommand):
    help = 'Export telefonního scénáře do JSON.'

    def add_arguments(self, parser):
        parser.add_argument('slug', type=str)
        parser.add_argument('-o', '--output', type=str, default='-', help='Výstupní soubor (- = stdout)')

    def handle(self, *args, **options):
        try:
            script = PhoneScript.objects.get(slug=options['slug'])
        except PhoneScript.DoesNotExist as exc:
            raise CommandError(f'Scénář {options["slug"]} neexistuje.') from exc

        payload = export_script_json(script)
        if options['output'] == '-':
            self.stdout.write(payload)
            return
        Path(options['output']).write_text(payload, encoding='utf-8')
        self.stdout.write(self.style.SUCCESS(f'Uloženo do {options["output"]}'))
