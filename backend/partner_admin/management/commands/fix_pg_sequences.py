"""
Po seedech s explicitním pk=… Postgres sequence často zůstane pozadu.
Tento příkaz synchronizuje identity/serial sekvence na MAX(id).
"""
from django.core.management.base import BaseCommand
from django.db import connection


# Tabulky, které seedují s pevným id / kopírují data
TABLES = [
    'salons_salon',
    'salons_cenikpolozka',
    'salons_novinka',
    'salons_oteviracidoba',
    'salons_salonobrazek',
    'rezervace_zamestnanec',
    'rezervace_rezervacninastaveni',
    'partner_admin_partnernastaveni',
    'flow_flowuser',
]


class Command(BaseCommand):
    help = 'Opraví Postgres sekvence (setval) po seedu s explicitními PK.'

    def handle(self, *args, **options):
        if connection.vendor != 'postgresql':
            self.stdout.write('Skip — jen PostgreSQL.')
            return
        fixed = 0
        with connection.cursor() as c:
            for table in TABLES:
                c.execute(
                    """
                    SELECT EXISTS (
                      SELECT 1 FROM information_schema.tables
                      WHERE table_schema = 'public' AND table_name = %s
                    )
                    """,
                    [table],
                )
                if not c.fetchone()[0]:
                    continue
                c.execute(
                    """
                    SELECT setval(
                      pg_get_serial_sequence(%s, 'id'),
                      COALESCE((SELECT MAX(id) FROM """ + table + """), 1),
                      true
                    )
                    """,
                    [table],
                )
                val = c.fetchone()[0]
                self.stdout.write(f'{table}: sequence → {val}')
                fixed += 1
        self.stdout.write(self.style.SUCCESS(f'Hotovo ({fixed} tabulek).'))
