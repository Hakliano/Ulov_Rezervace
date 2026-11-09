from django.core.management.base import BaseCommand

from jadro.bunny_client import BunnyStorageError, get_bunny_client


class Command(BaseCommand):
    help = 'Ověří PUT/GET/DELETE pod prefixem postak/ (LOCAL integrace).'

    def handle(self, *args, **options):
        client = get_bunny_client()
        if not client:
            self.stderr.write('Nastavte POSTAK_BUNNY_ENABLED a POSTAK_BUNNY_ACCESS_KEY v .env.')
            return
        test_key = '_smoke/integrace.txt'
        payload = b'postak-bunny-smoke\n'
        try:
            client.put(test_key, payload, content_type='text/plain')
            if client.get(test_key) != payload:
                raise BunnyStorageError('GET nevrátilo očekávaná data.')
            client.delete(test_key)
        except BunnyStorageError as exc:
            self.stderr.write(self.style.ERROR(str(exc)))
            return
        self.stdout.write(self.style.SUCCESS('Bunny Storage OK (postak prefix).'))
