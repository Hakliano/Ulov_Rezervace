from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from partner_admin.models import PartnerNastaveni
from salons.models import Salon


class Command(BaseCommand):
    help = 'Naplní lokální demo údaje superadmin panelu. V produkci se nespustí.'

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('Demo platební data lze vytvořit pouze při DEBUG=True.')

        dnes = timezone.localdate()
        for salon in Salon.objects.order_by('id'):
            partner, _ = PartnerNastaveni.objects.get_or_create(salon=salon)
            partner.domena = f'demo{salon.id}.ulovklienty.cz'
            partner.tarif = 'Partner pro váš salon'
            partner.fakturacni_email = salon.email
            partner.variabilni_symbol = str(8000000000 + salon.id)
            partner.periodicita = (
                PartnerNastaveni.PERIODA_ROK
                if salon.id % 3 == 0
                else PartnerNastaveni.PERIODA_MESIC
            )
            partner.castka = (
                Decimal('4990.00')
                if partner.periodicita == PartnerNastaveni.PERIODA_ROK
                else Decimal('499.00')
            )
            if salon.id == 1:
                partner.dalsi_splatnost = dnes - timedelta(days=6)
            elif salon.id == 2:
                partner.dalsi_splatnost = dnes
            elif salon.id == 3:
                partner.dalsi_splatnost = None
            else:
                partner.dalsi_splatnost = dnes + timedelta(days=salon.id)
            partner.save()

        self.stdout.write(self.style.SUCCESS('Lokální demo partner data byla připravena.'))
