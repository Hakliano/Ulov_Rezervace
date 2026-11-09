import json
import zipfile
from pathlib import Path

from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand

from jadro.dokumentace_models import DokumentSoubor
from jadro.models import EmailKonceptPriloha, Profil


class Command(BaseCommand):
    help = 'Záloha souborů z úložiště do ZIP + manifest JSON (nezávislé na LIVE).'

    def add_arguments(self, parser):
        parser.add_argument('vystup', type=str, help='Cesta k .zip souboru')

    def handle(self, *args, **options):
        out = Path(options['vystup'])
        manifest = []
        with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            for row in self._rows():
                name = row['storage_name']
                if not name or not default_storage.exists(name):
                    row['chyba'] = 'chybi'
                    manifest.append(row)
                    continue
                with default_storage.open(name, 'rb') as f:
                    data = f.read()
                arc = f"files/{row['typ']}/{row['id']}_{Path(name).name}"
                zf.writestr(arc, data)
                row['archiv'] = arc
                manifest.append(row)
            zf.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
        self.stdout.write(self.style.SUCCESS(f'Záloha uložena: {out}'))

    def _rows(self):
        for p in Profil.objects.exclude(foto=''):
            yield {'typ': 'profil', 'id': p.user_id, 'storage_name': p.foto.name}
        for d in DokumentSoubor.objects.iterator():
            yield {'typ': 'dokument', 'id': d.pk, 'storage_name': d.soubor.name}
        for a in EmailKonceptPriloha.objects.iterator():
            yield {'typ': 'koncept', 'id': a.pk, 'storage_name': a.soubor.name}
