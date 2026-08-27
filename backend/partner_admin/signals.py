from django.db.models.signals import post_save
from django.dispatch import receiver

from salons.models import Salon

from .models import PartnerNastaveni, vychozi_variabilni_symbol


@receiver(post_save, sender=Salon)
def vytvor_partner_nastaveni(sender, instance, created, **kwargs):
    if created:
        vs = vychozi_variabilni_symbol(instance.id) or None
        if vs and PartnerNastaveni.objects.filter(variabilni_symbol=vs).exists():
            vs = None
        PartnerNastaveni.objects.get_or_create(
            salon=instance,
            defaults={
                'fakturacni_email': instance.email,
                'variabilni_symbol': vs,
            },
        )
        from .services import primarni_ulov_ucet

        cislo = primarni_ulov_ucet()
        if cislo:
            PartnerNastaveni.objects.filter(salon=instance).update(ulov_cislo_uctu=cislo)
