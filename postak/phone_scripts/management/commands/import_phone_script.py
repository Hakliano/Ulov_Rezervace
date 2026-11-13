from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from phone_scripts.services.import_export import ImportError as ScriptImportError
from phone_scripts.services.import_export import import_script_from_dict, import_script_json
from phone_scripts.services.snapshot import publish_script


class Command(BaseCommand):
    help = 'Import telefonního scénáře z JSON souboru.'

    def add_arguments(self, parser):
        parser.add_argument('path', type=str, help='Cesta k JSON souboru')
        parser.add_argument('--slug', type=str, default=None, help='Přepsat slug')
        parser.add_argument('--replace', action='store_true', help='Nahradit existující scénář')
        parser.add_argument('--dry-run', action='store_true', help='Jen parsování bez zápisu')
        parser.add_argument('--publish', action='store_true', help='Po importu publikovat')

    def handle(self, *args, **options):
        path = Path(options['path'])
        if not path.is_file():
            raise CommandError(f'Soubor neexistuje: {path}')
        raw = path.read_text(encoding='utf-8')
        if options['dry_run']:
            import json

            try:
                data = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise CommandError(str(exc)) from exc
            from phone_scripts.services.validate import validate_script
            from phone_scripts.models import PhoneScript

            self.stdout.write('Dry-run: struktura JSON je platná.')
            self.stdout.write(f"Kroků: {len(data.get('steps') or {})}")
            return

        try:
            script = import_script_json(
                raw,
                slug=options.get('slug'),
                replace=options['replace'],
            )
        except ScriptImportError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS(f'Importován scénář {script.slug} (id={script.pk}).'))

        if options['publish']:
            ok, notes = publish_script(script)
            if not ok:
                raise CommandError('Publikace selhala: ' + '; '.join(notes))
            if notes:
                self.stdout.write(self.style.WARNING('; '.join(notes)))
            self.stdout.write(self.style.SUCCESS(f'Publikováno v{script.version}.'))
