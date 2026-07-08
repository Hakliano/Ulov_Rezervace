from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from rezervace.services.zivotni_cyklus import proved_zivotni_cyklus


class Command(BaseCommand):
    help = (
        'Životní cyklus rezervace: e-maily → děkovný e-mail → anonymizace → smazání '
        '(cron každou hodinu)'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--posun-hodin',
            type=int,
            default=0,
            help=(
                'Simulovaný posun času o N hodin (jen pro testování celého cyklu na '
                'testovacích datech). V produkci nechte 0.'
            ),
        )

    def handle(self, *args, **options):
        posun = options.get('posun_hodin', 0)
        now = timezone.now() + timedelta(hours=posun) if posun else None
        if posun:
            self.stdout.write(self.style.WARNING(
                f'POZOR: běh se simulovaným časem +{posun} h (test).'
            ))
        vysledek = proved_zivotni_cyklus(now=now)
        v = vysledek['vycisteno']
        self.stdout.write(self.style.SUCCESS(
            f'E-maily: {vysledek["emaily_odeslano"]}, '
            f'anonymizováno: {vysledek["anonymizovano"]}, '
            f'smazáno (soft): {vysledek["smazano_soft"]}. '
            f'Úklid — audit: {v["audit"]}, historie: {v["historie"]}, '
            f'rezervace: {v["rezervace"]}, NO-show: {v["noshow"]}, sessiony: {v["sessiony"]}.',
        ))
