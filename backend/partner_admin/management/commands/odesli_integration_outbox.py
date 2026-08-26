"""Dohrání outboxu FLOW → Materiálník. Rezervace se kvůli tomu nikdy nevrací."""

from django.core.management.base import BaseCommand
from django.utils import timezone

from partner_admin.materialnik_client import (
    MaterialnikRejected,
    MaterialnikUnavailable,
    post_event,
)
from partner_admin.models import IntegrationOutbox, PartnerModul, MODUL_MATERIALNIK
from partner_admin.services_moduly import partner_modul


class Command(BaseCommand):
    help = 'Odešle čekající integration outbox eventy do Materiálníku.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=50)

    def handle(self, *args, **options):
        limit = options['limit']
        ted = timezone.now()
        qs = IntegrationOutbox.objects.filter(status=IntegrationOutbox.STAV_PENDING).order_by('created_at')
        qs = qs.filter(models_q_due(ted))[:limit]
        sent = failed = skipped = 0
        for row in qs:
            modul = partner_modul(row.salon, MODUL_MATERIALNIK)
            if not modul or modul.status != PartnerModul.STAV_ACTIVE:
                row.status = IntegrationOutbox.STAV_SKIPPED
                row.last_error = 'tenant_inactive'
                row.save(update_fields=['status', 'last_error'])
                skipped += 1
                continue
            try:
                occurred = (row.payload or {}).get('occurred_at') or ted.isoformat()
                post_event(
                    payload=row.payload,
                    hmac_key=modul.hmac_key,
                    event_id=row.event_id,
                    timestamp=occurred,
                )
            except MaterialnikUnavailable as exc:
                row.attempts += 1
                row.last_error = str(exc.detail)[:400]
                row.next_attempt_at = ted
                if row.attempts >= 20:
                    row.status = IntegrationOutbox.STAV_FAILED
                row.save(update_fields=['attempts', 'last_error', 'next_attempt_at', 'status'])
                failed += 1
                continue
            except MaterialnikRejected as exc:
                row.attempts += 1
                row.status = IntegrationOutbox.STAV_FAILED
                row.last_error = str(exc.detail)[:400]
                row.save(update_fields=['attempts', 'status', 'last_error'])
                failed += 1
                continue
            row.status = IntegrationOutbox.STAV_SENT
            row.sent_at = ted
            row.last_error = ''
            row.save(update_fields=['status', 'sent_at', 'last_error'])
            sent += 1
        self.stdout.write(f'sent={sent} failed={failed} skipped={skipped}')


def models_q_due(ted):
    from django.db.models import Q
    return Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=ted)
