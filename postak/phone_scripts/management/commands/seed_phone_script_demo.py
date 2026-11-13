from django.core.management.base import BaseCommand

from phone_scripts.demo_content import demo_hya_payload, demo_modernik_payload
from phone_scripts.services.import_export import import_script_from_dict
from phone_scripts.services.snapshot import publish_script


class Command(BaseCommand):
    help = 'Vytvoří a publikuje demonstrační scénáře Moderník a HereYouAre.'

    def handle(self, *args, **options):
        for payload in (demo_modernik_payload(), demo_hya_payload()):
            script = import_script_from_dict(payload, replace=True)
            ok, notes = publish_script(script)
            if not ok:
                self.stderr.write(f'CHYBA {script.slug}: ' + '; '.join(notes))
                continue
            self.stdout.write(
                self.style.SUCCESS(f'{script.slug} publikováno (v{script.version}, kroků ~{script.steps.count()}).')
            )
            for w in notes:
                self.stdout.write(self.style.WARNING(w))
