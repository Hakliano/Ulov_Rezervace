from django.core.management.base import BaseCommand, CommandError

from archivnik.pawcare_showcase import (
    DEFAULT_SALON_ID,
    PawCareShowcaseError,
    seed_pawcare,
)


class Command(BaseCommand):
    help = (
        'P6.0 showcase kartotéka pro existující salon 10 PawCare. '
        'Nového partnera nezakládá. Bez --reset existující kartotéku nepřepisuje. '
        'Nespouštět na LIVE. Nespouštět --reset z běžného deploye.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--salon-id', type=int, default=DEFAULT_SALON_ID)
        parser.add_argument(
            '--reset',
            action='store_true',
            help=(
                'Vědomě smaže jen kartotéku tohoto PawCare salonu a nasadí dataset znovu. '
                'Nesmí se volat z deploy-staging.sh. Nespouštět na LIVE.'
            ),
        )

    def handle(self, *args, **options):
        try:
            result = seed_pawcare(salon_id=options['salon_id'], reset=options['reset'])
        except PawCareShowcaseError as exc:
            raise CommandError(str(exc)) from exc
        skip = ' skip=1' if result.get('skip') else ''
        reset = ' reset=1' if result.get('reset') else ''
        self.stdout.write(
            f"salon_id={result['salon_id']} "
            f"zakaznici={result['zakaznici']} objekty={result['objekty']} "
            f"zapisy={result['zapisy']} pripominky={result['pripominky']} "
            f"pripominky_aktivni={result['pripominky_aktivni']} "
            f"soubory={result['soubory']}{skip}{reset}"
        )
