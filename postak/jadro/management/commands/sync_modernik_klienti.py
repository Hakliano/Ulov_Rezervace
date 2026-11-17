import sys

from django.core.management.base import BaseCommand

from jadro.klienti_sync import synchronizuj_modernik_jako_tlacitko
from jadro.sync_lock import SyncAlreadyRunning, sync_file_lock


class Command(BaseCommand):
    help = 'Noční synchronizace klientů Moderníku (stejná logika jako ruční tlačítko)'

    def handle(self, *args, **options):
        try:
            with sync_file_lock('modernik'):
                stats = synchronizuj_modernik_jako_tlacitko(nocni=True)
        except SyncAlreadyRunning:
            self.stderr.write('Moderník sync already running')
            sys.exit(0)
        self.stdout.write(self.style.SUCCESS(str(stats)))
