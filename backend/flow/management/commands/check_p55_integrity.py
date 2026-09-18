"""DB integrity report pro P5.5 acceptance salon."""
from django.core.management.base import BaseCommand

from flow.p55_acceptance import DEFAULT_SALON_ID, integrity_report, standalone_salon
from salons.models import Salon


class Command(BaseCommand):
    help = 'P5.5 integrita kartotéky: duplicity, orphany, cross-tenant, legacy counts.'

    def add_arguments(self, parser):
        parser.add_argument('--salon-id', type=int, default=DEFAULT_SALON_ID)
        parser.add_argument('--extra-salon-id', type=int, default=0)

    def handle(self, *args, **options):
        salon = Salon.objects.filter(pk=options['salon_id']).first()
        if not salon:
            raise SystemExit(f"Salon {options['salon_id']} neexistuje.")
        extra = None
        extra_id = options['extra_salon_id']
        if extra_id:
            extra = Salon.objects.filter(pk=extra_id).first()
        else:
            extra = standalone_salon()
        report = integrity_report(salon, extra_salon=extra)
        self.stdout.write(
            f"salon={report['salon_id']} customers={report['customers']} "
            f"objects={report['objects']} entries={report['entries']} "
            f"reminders={report['reminders']} assets={report['assets']} "
            f"dupes={len(report['duplicate_emails'])} "
            f"orphan_objects={report['orphan_objects']} "
            f"orphan_entries={report['orphan_entries']} "
            f"object_other_salon={report['object_customer_other_salon']} "
            f"entry_object_other={report['entry_object_other_customer']} "
            f"cross={report['global_cross_tenant']} "
            f"legacy={report['legacy']} illegal={report['illegal']}"
        )
        extra_row = report.get('extra_salon')
        if extra_row:
            self.stdout.write(
                f"extra_salon={extra_row['salon_id']} customers={extra_row['customers']} "
                f"shared_uuids={extra_row['shared_customer_uuids']}"
            )
        if report['illegal']:
            raise SystemExit(f"P5.5 integrity FAIL illegal={report['illegal']}")
        self.stdout.write(self.style.SUCCESS('P5.5 integrity PASS'))
