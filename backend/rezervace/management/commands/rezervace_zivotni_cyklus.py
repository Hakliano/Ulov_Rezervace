from django.core.management.base import BaseCommand

from rezervace.services.zivotni_cyklus import proved_zivotni_cyklus


class Command(BaseCommand):
    help = (
        'Životní cyklus rezervace: e-maily → děkovný e-mail → anonymizace → smazání '
        '(cron každou hodinu)'
    )

    def handle(self, *args, **options):
        vysledek = proved_zivotni_cyklus()
        v = vysledek['vycisteno']
        self.stdout.write(self.style.SUCCESS(
            f'E-maily: {vysledek["emaily_odeslano"]}, '
            f'anonymizováno: {vysledek["anonymizovano"]}, '
            f'smazáno (soft): {vysledek["smazano_soft"]}. '
            f'Úklid — audit: {v["audit"]}, historie: {v["historie"]}, '
            f'rezervace: {v["rezervace"]}, NO-show: {v["noshow"]}, sessiony: {v["sessiony"]}.',
        ))
