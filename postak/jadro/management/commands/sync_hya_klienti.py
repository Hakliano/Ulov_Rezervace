from django.core.management.base import BaseCommand

from jadro.klienti_sync import synchronizuj_hya


class Command(BaseCommand):
    help = 'Noční / ruční synchronizace klientů HYA do cache Pošťáku'

    def handle(self, *args, **options):
        stats = synchronizuj_hya(nocni=True)
        self.stdout.write(self.style.SUCCESS(str(stats)))