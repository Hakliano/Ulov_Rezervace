from django.core.management.base import BaseCommand

from jadro.bunny_client import BunnyStorageError, get_bunny_client
from jadro.dokumentace_models import DokumentSoubor
from jadro.models import EmailKonceptPriloha, Profil


class Command(BaseCommand):
    help = 'Inventura souborů Pošťáka (DB + volitelně Bunny pod prefixem postak/).'

    def add_arguments(self, parser):
        parser.add_argument('--remote', action='store_true', help='Vypsat objekty ze Storage API')

    def handle(self, *args, **options):
        self.stdout.write('=== Záznamy v databázi ===')
        for p in Profil.objects.exclude(foto='').iterator():
            self.stdout.write(f'profil\t{p.user_id}\t{p.foto.name}')
        for d in DokumentSoubor.objects.iterator():
            self.stdout.write(f'dokument\t{d.pk}\t{d.soubor.name}')
        for a in EmailKonceptPriloha.objects.iterator():
            self.stdout.write(f'koncept\t{a.pk}\t{a.soubor.name}')

        if not options['remote']:
            return
        client = get_bunny_client()
        if not client:
            self.stderr.write('Bunny není aktivní (POSTAK_BUNNY_ENABLED + klíč).')
            return
        try:
            keys = client.list_prefix('')
        except BunnyStorageError as exc:
            self.stderr.write(f'Remote list selhal: {exc}')
            return
        self.stdout.write('=== Objekty na Bunny ===')
        for key in sorted(keys):
            self.stdout.write(key)
