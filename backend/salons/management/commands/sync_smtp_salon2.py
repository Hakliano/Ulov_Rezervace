"""Zkopíruje SMTP nastavení ze salonu 2 (Studio Krása) do salonů 3 a 4."""

from django.core.management.base import BaseCommand

from rezervace.models import RezervacniNastaveni
from rezervace.services.emails import get_email_config
from salons.models import Salon

SMTP_FIELDS = ('smtp_host', 'smtp_port', 'smtp_use_ssl', 'smtp_user', 'smtp_password')


class Command(BaseCommand):
    help = 'Zkopíruje SMTP ze salonu 2 do salonů 3 a 4 (pro testování e-mailů)'

    def handle(self, *args, **options):
        try:
            src_salon = Salon.objects.get(pk=2)
        except Salon.DoesNotExist:
            self.stderr.write(self.style.ERROR('Salon 2 (Studio Krása) neexistuje.'))
            return

        src_nast, _ = RezervacniNastaveni.objects.get_or_create(salon=src_salon)
        cfg = get_email_config(src_salon)

        if not cfg['smtp_ready']:
            self.stderr.write(self.style.ERROR(
                'Salon 2 nemá SMTP — nastavte v administraci webu (⚙ → E-mail) nebo v backend/.env',
            ))
            return

        if not src_nast.smtp_password:
            src_nast.smtp_host = cfg['host']
            src_nast.smtp_port = cfg['port']
            src_nast.smtp_use_ssl = cfg['use_ssl']
            src_nast.smtp_user = cfg['user']
            src_nast.smtp_password = cfg['password']
            src_nast.save(update_fields=list(SMTP_FIELDS))

        for pk in (3, 4):
            try:
                salon = Salon.objects.get(pk=pk)
            except Salon.DoesNotExist:
                self.stdout.write(self.style.WARNING(f'Salon {pk} neexistuje, přeskakuji.'))
                continue
            nast, _ = RezervacniNastaveni.objects.get_or_create(salon=salon)
            for field in SMTP_FIELDS:
                setattr(nast, field, getattr(src_nast, field))
            nast.save(update_fields=list(SMTP_FIELDS))
            self.stdout.write(self.style.SUCCESS(
                f'SMTP zkopirovano -> salon {pk} ({salon.name}), odesilatel: {salon.email}',
            ))
