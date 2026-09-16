"""P5.5 STAGING acceptance sada. Bez flagu nic nemaže."""
from django.core.management.base import BaseCommand

from flow.p55_acceptance import (
    DEFAULT_SALON_ID,
    TAG,
    config_snapshot,
    integrity_report,
    legacy_counts,
    seed_acceptance,
    standalone_salon,
    tagged_customers,
    wipe_p53,
    wipe_salon_kartoteka,
    wipe_tagged,
)
from partner_admin.models import MODUL_ARCHIVNIK, PartnerModul
from salons.models import Salon


class Command(BaseCommand):
    help = (
        'P5.5 acceptance kartotéka. Bez --reset/--cleanup-salon existující P5.5 sadu nepřepisuje. '
        'Nespouštět destruktivní flagy z běžného deploye.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--salon-id', type=int, default=DEFAULT_SALON_ID)
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Smaže jen P5.5 označená data tohoto salonu a nasadí sadu znovu.',
        )
        parser.add_argument(
            '--cleanup-p53',
            action='store_true',
            help='Smaže jen P5.3 testovací kartotéku (@p53.ulov.local / P5.3) tohoto salonu.',
        )
        parser.add_argument(
            '--cleanup-salon',
            action='store_true',
            help=(
                'Smaže veškerou kartotéku (Customer/Object/Entry/Reminder/Asset) tohoto salonu. '
                'Obory, ObjectTypes, CustomFields, PartnerModul a FLOW účty nechá.'
            ),
        )
        parser.add_argument(
            '--with-pager',
            action='store_true',
            help='Doplní filler zákazníky, aby FLOW seznam měl víc než jednu stránku (page_size 50).',
        )

    def handle(self, *args, **options):
        salon = Salon.objects.filter(pk=options['salon_id']).first()
        if not salon:
            raise SystemExit(f"Salon {options['salon_id']} neexistuje.")

        before_cfg = config_snapshot(salon)
        before_legacy = legacy_counts(salon)
        wiped = {}

        if options['cleanup_salon']:
            wiped['salon'] = wipe_salon_kartoteka(salon)
            self.stdout.write(
                f"cleanup-salon customers_deleted={wiped['salon']['customers_deleted']} "
                f"asset_keys={len(wiped['salon']['asset_keys'])}"
            )
            for key in wiped['salon']['asset_keys']:
                self.stdout.write(f'  bunny_or_local {key}')
        else:
            if options['cleanup_p53']:
                wiped['p53'] = wipe_p53(salon)
                self.stdout.write(
                    f"cleanup-p53 customers_deleted={wiped['p53']['customers_deleted']} "
                    f"asset_keys={len(wiped['p53']['asset_keys'])}"
                )
            if options['reset']:
                wiped['tagged'] = wipe_tagged(salon)
                self.stdout.write(
                    f"reset-p55 customers_deleted={wiped['tagged']['customers_deleted']} "
                    f"asset_keys={len(wiped['tagged']['asset_keys'])}"
                )

        existing = tagged_customers(salon).count()
        if existing and not options['reset'] and not options['cleanup_salon']:
            report = integrity_report(salon, extra_salon=standalone_salon())
            self.stdout.write(
                f'skip_seed salon={salon.id} p55_customers={existing} tag={TAG} '
                f'(použijte --reset pro přepis vlastní sady)'
            )
            self._print_report(salon, before_cfg, before_legacy, report, created=None)
            return

        created = seed_acceptance(salon, with_pager=options['with_pager'])
        after_cfg = config_snapshot(salon)
        after_legacy = legacy_counts(salon)
        report = integrity_report(salon, extra_salon=standalone_salon())
        modul = PartnerModul.objects.filter(
            salon=salon, modul__kod=MODUL_ARCHIVNIK, status=PartnerModul.STAV_ACTIVE,
        ).exists()
        self.stdout.write(self.style.SUCCESS(
            f"P5.5 seed salon={salon.id} login={created['owner_login']} "
            f"archivnik_active={int(modul)} "
            f"jan={created['jan'].uuid} petr={created['petr'].uuid} "
            f"anna={created['anna'].uuid} karel={created['karel'].uuid} "
            f"walkin={created['walkin'].uuid} "
            f"vlasy={created['vlasy'].uuid} entry_a={created['entry_a'].uuid} "
            f"rez_f={created['rez_f'].id} rez_g={created['rez_g'].id} rez_h={created['rez_h'].id} "
            f"fillers={created['fillers']} asset={getattr(created['asset'], 'uuid', None)}"
        ))
        if created['asset_error']:
            self.stdout.write(self.style.WARNING(f"asset_skip {created['asset_error']}"))
        self._print_report(salon, before_cfg, before_legacy, report, created=created)
        if after_cfg != before_cfg and not options['cleanup_salon']:
            self.stdout.write(self.style.WARNING(
                f'config changed before={before_cfg} after={after_cfg}'
            ))
        if after_legacy != before_legacy:
            self.stdout.write(self.style.WARNING(
                f'legacy changed before={before_legacy} after={after_legacy}'
            ))

    def _print_report(self, salon, before_cfg, before_legacy, report, created):
        self.stdout.write(
            f"integrity illegal={report['illegal']} "
            f"customers={report['customers']} objects={report['objects']} "
            f"entries={report['entries']} reminders={report['reminders']} "
            f"assets={report['assets']} dupes={len(report['duplicate_emails'])} "
            f"legacy={report['legacy']} config={report['config']} "
            f"legacy_before={before_legacy} config_before={before_cfg}"
        )
        extra = report.get('extra_salon')
        if extra:
            self.stdout.write(
                f"standalone salon={extra['salon_id']} customers={extra['customers']} "
                f"shared_uuids={extra['shared_customer_uuids']}"
            )
