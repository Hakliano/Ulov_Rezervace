import secrets

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Vytvoří nebo resetuje lokální superadmin účet a vypíše jednorázové heslo.'

    def add_arguments(self, parser):
        parser.add_argument('--username', default='superadmin')

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('Tento příkaz lze použít pouze při DEBUG=True.')

        username = options['username'].strip()
        password = secrets.token_urlsafe(18)
        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=username,
            defaults={'email': 'local-superadmin@localhost'},
        )
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.set_password(password)
        user.save()
        action = 'vytvořen' if created else 'resetován'
        self.stdout.write(self.style.SUCCESS(f'Lokální superadmin byl {action}.'))
        self.stdout.write(f'Uživatel: {username}')
        self.stdout.write(f'Jednorázové heslo: {password}')
