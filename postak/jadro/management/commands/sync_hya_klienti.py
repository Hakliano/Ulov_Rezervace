import sys

from django.core.management.base import BaseCommand

from jadro.klienti_sync import synchronizuj_hya_jako_tlacitko
from jadro.sync_lock import SyncAlreadyRunning, sync_file_lock


class Command(BaseCommand):
    help = 'Noční synchronizace klientů HYA (stejná logika jako ruční tlačítko)'

    def handle(self, *args, **options):
        try:
            with sync_file_lock('hya'):
                stats = synchronizuj_hya_jako_tlacitko(nocni=True)
        except SyncAlreadyRunning:
            self.stderr.write('HYA sync already running')
            sys.exit(0)
        self.stdout.write(self.style.SUCCESS(str(stats)))