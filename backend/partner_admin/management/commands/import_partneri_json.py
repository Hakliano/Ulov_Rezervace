"""Import partnerů z JSON (Moderník / PotencialniKontakt) — podporuje DRY RUN a zálohu DB."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from partner_admin.partner_import import ImportReport, ImportZamcenError, nacti_soubory, spust_import, spust_import_commit


class Command(BaseCommand):
    help = 'Bezpečný import partneri_export_doplneny.json a partneri_zbyvajicich_676.json (MODERNÍK).'

    def add_arguments(self, parser):
        parser.add_argument(
            'soubory',
            nargs='+',
            type=str,
            help='Cesty k JSON souborům',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Jen report, nic nezapisovat (výchozí pokud není --commit).',
        )
        parser.add_argument(
            '--commit',
            action='store_true',
            help='Skutečný zápis do databáze.',
        )
        parser.add_argument(
            '--backup',
            action='store_true',
            help='Před commitem zkopírovat SQLite DB (jen sqlite3).',
        )
        parser.add_argument(
            '--json-report',
            type=str,
            default='',
            help='Volitelně uložit report do JSON souboru.',
        )

    def handle(self, *args, **options):
        commit = bool(options['commit'])
        dry_run = not commit or bool(options['dry_run'])
        if commit and options['dry_run']:
            raise CommandError('Nelze kombinovat --commit a --dry-run.')
        if commit and not options['backup']:
            raise CommandError('Před --commit je povinný parametr --backup.')

        cesty = [Path(p) for p in options['soubory']]
        for cesta in cesty:
            if not cesta.is_file():
                raise CommandError(f'Soubor neexistuje: {cesta}')

        if commit and options['backup']:
            self._zaloha_sqlite()

        payloads = nacti_soubory(cesty)
        if commit:
            try:
                report = spust_import_commit(payloads)
            except ImportZamcenError as exc:
                raise CommandError(str(exc)) from exc
        else:
            report = spust_import(payloads, dry_run=True)
        self._vypis(report, dry_run=dry_run)

        out = (options.get('json_report') or '').strip()
        if out:
            Path(out).write_text(
                json.dumps(report.as_dict(), ensure_ascii=False, indent=2),
                encoding='utf-8',
            )
            self.stdout.write(f'Report uložen: {out}')

    def _zaloha_sqlite(self):
        db = settings.DATABASES.get('default', {})
        engine = db.get('ENGINE', '')
        if not engine.endswith('sqlite3'):
            self.stdout.write(self.style.WARNING('Záloha: jen SQLite (jiný engine přeskočen).'))
            return
        name = db.get('NAME')
        if not name:
            return
        zdroj = Path(name)
        if not zdroj.is_file():
            return
        cas = datetime.now().strftime('%Y%m%d-%H%M%S')
        cil = zdroj.with_suffix(zdroj.suffix + f'.backup-{cas}')
        shutil.copy2(zdroj, cil)
        self.stdout.write(self.style.SUCCESS(f'Záloha DB: {cil}'))

    def _vypis(self, report: ImportReport, *, dry_run: bool):
        rezim = 'DRY RUN' if dry_run else 'COMMIT'
        self.stdout.write(self.style.MIGRATE_HEADING(f'Import partnerů [{rezim}]'))
        d = report.as_dict()
        for klic in (
            'nacteno', 'UPDATE', 'INSERT', 'BEZE_ZMENY', 'KONFLIKT',
            'duplicity_json', 'pred_pocet', 'po_pocet',
        ):
            self.stdout.write(f'  {klic}: {d[klic]}')
        if report.statusy_zmeneny:
            self.stdout.write(self.style.ERROR('  VAROVÁNÍ: změněné statusy: ' + ', '.join(report.statusy_zmeneny[:10])))
        else:
            self.stdout.write(self.style.SUCCESS('  Kontrola statusů: beze změny.'))
        if report.neplatne:
            self.stdout.write('  Neplatné: ' + '; '.join(report.neplatne[:8]))
        if report.nejednoznacne_priklady:
            self.stdout.write('  Nejednoznačné (ukázka): ' + ', '.join(report.nejednoznacne_priklady[:5]))