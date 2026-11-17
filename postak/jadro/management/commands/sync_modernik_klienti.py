from django.core.management.base import BaseCommand

from jadro.klienti_sync import synchronizuj_modernik


class Command(BaseCommand):
    help = 'Noční / ruční synchronizace klientů Moderníku do cache Pošťáku'

    def handle(self, *args, **options):
        stats = synchronizuj_modernik(nocni=True)
        self.stdout.write(self.style.SUCCESS(str(stats)))
