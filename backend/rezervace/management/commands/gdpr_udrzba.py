from django.core.management.base import BaseCommand

from rezervace.services.zivotni_cyklus import proved_zivotni_cyklus


class Command(BaseCommand):
    help = 'Alias pro rezervace_zivotni_cyklus (zpětná kompatibilita)'

    def handle(self, *args, **options):
        vysledek = proved_zivotni_cyklus()
        v = vysledek['vycisteno']
        self.stdout.write(self.style.SUCCESS(
            f'[gdpr_udrzba → životní cyklus] anonymizováno: {vysledek["anonymizovano"]}, '
            f'smazáno: {vysledek["smazano_soft"]}, úklid rezervací: {v["rezervace"]}.',
        ))
