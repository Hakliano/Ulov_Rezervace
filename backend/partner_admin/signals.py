from django.db.models.signals import post_save
from django.dispatch import receiver

from salons.models import Salon

from .models import PartnerNastaveni


@receiver(post_save, sender=Salon)
def vytvor_partner_nastaveni(sender, instance, created, **kwargs):
    if created:
        PartnerNastaveni.objects.get_or_create(
            salon=instance,
            defaults={'fakturacni_email': instance.email},
        )
