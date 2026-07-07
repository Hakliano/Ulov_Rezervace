from django.core.management.base import BaseCommand

from rezervace.services.zivotni_cyklus import proved_zivotni_cyklus


class Command(BaseCommand):
    help = 'Alias pro rezervace_zivotni_cyklus (zpětná kompatibilita cronu)'

    def handle(self, *args, **options):
        vysledek = proved_zivotni_cyklus()
        self.stdout.write(self.style.SUCCESS(
            f'[odesli_pripominky → životní cyklus] e-maily: {vysledek["emaily_odeslano"]}, '
            f'anonymizováno: {vysledek["anonymizovano"]}.',
        ))
