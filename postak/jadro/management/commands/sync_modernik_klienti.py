from django.core.management.base import BaseCommand

from jadro.klienti_sync import synchronizuj_klienty


class Command(BaseCommand):
    help = 'Ruční / noční synchronizace klientů Moderníku a HYA do cache Pošťáku'

    def handle(self, *args, **options):
        stats = synchronizuj_klienty(nocni=True)
        self.stdout.write(self.style.SUCCESS(str(stats)))
