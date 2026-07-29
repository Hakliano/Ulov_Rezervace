"""
Unikátní přihlašovací e-maily majitelů napříč všemi salony.

Použití před staging/LIVE:
  python manage.py ensure_unique_owner_emails --dry-run
  python manage.py ensure_unique_owner_emails
"""
from __future__ import annotations

from django.core.management.base import BaseCommand

from rezervace.services.owner_emails import (
    apply_owner_email_fixes,
    plan_owner_email_fixes,
)


class Command(BaseCommand):
    help = 'Přepíše neunikátní / ne-e-mail loginy majitelů na unikátní e-maily.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Jen vypíše plán změn, nic neukládá.',
        )

    def handle(self, *args, **options):
        dry = options['dry_run']
        plan = plan_owner_email_fixes()
        if not plan:
            self.stdout.write(self.style.SUCCESS('OK — všichni majitelé už mají unikátní e-mail login.'))
            return

        self.stdout.write(f'Nalezeno {len(plan)} majitelů k úpravě:\n')
        for row in plan:
            self.stdout.write(
                f"  salon {row['salon_id']} ({row['salon_name']}): "
                f"{row['old']!r} → {row['new']!r}  [{row['reason']}]"
            )

        if dry:
            self.stdout.write(self.style.WARNING('\nDry-run — žádné změny. Spusť bez --dry-run pro zápis.'))
            return

        changed = apply_owner_email_fixes(plan)
        self.stdout.write(self.style.SUCCESS(f'\nHotovo — upraveno {changed} majitelů.'))
