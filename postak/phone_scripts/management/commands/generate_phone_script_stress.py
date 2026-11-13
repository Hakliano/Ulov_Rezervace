from django.core.management.base import BaseCommand, CommandError

from phone_scripts.demo_content import build_stress_payload
from phone_scripts.services.import_export import import_script_from_dict
from phone_scripts.services.snapshot import publish_script


class Command(BaseCommand):
    help = 'Vygeneruje zátěžový scénář (výchozí 180 kroků) pro test výkonu.'

    def add_arguments(self, parser):
        parser.add_argument('--steps', type=int, default=180)
        parser.add_argument('--slug', type=str, default='stress-test')
        parser.add_argument('--publish', action='store_true', default=True)

    def handle(self, *args, **options):
        payload = build_stress_payload(slug=options['slug'], steps_count=options['steps'])
        script = import_script_from_dict(payload, replace=True)
        if options['publish']:
            ok, notes = publish_script(script)
            if not ok:
                raise CommandError('; '.join(notes))
            for w in notes:
                self.stdout.write(self.style.WARNING(w))
        self.stdout.write(
            self.style.SUCCESS(
                f'Zátěžový scénář {script.slug}: {options["steps"]} kroků, v{script.version}.'
            )
        )
