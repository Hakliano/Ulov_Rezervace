"""Jednorázové faktury partnerovi — bez vlivu na předplatné."""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .faktura import (
    dalsi_cislo_faktury,
    odesli_extra_fakturu_partnerovi,
    uloz_fakturu_extra,
    vs_extra_z_cisla,
)
from .models import ExtraFaktura
from .services import log_superadmin


def vytvor_extra_fakturu(salon, user, *, popis, castka, stav, poznamka='', odeslat_email=False):
    dnes = timezone.localdate()
    k_uhrade = stav == ExtraFaktura.STAV_K_UHRADE
    with transaction.atomic():
        cislo = dalsi_cislo_faktury(dnes.year)
        faktura = ExtraFaktura.objects.create(
            salon=salon,
            cislo_faktury=cislo,
            variabilni_symbol=vs_extra_z_cisla(cislo),
            popis=popis.strip(),
            castka=castka,
            stav=stav,
            datum_vystaveni=dnes,
            datum_splatnosti=(dnes + timedelta(days=14)) if k_uhrade else None,
            datum_uhrady=None if k_uhrade else dnes,
            poznamka=(poznamka or '').strip(),
            vytvoril=user,
        )
        uloz_fakturu_extra(faktura)

    poslat = odeslat_email or k_uhrade
    mail_ok, mail_detail = True, ''
    if poslat:
        mail_ok, mail_detail = odesli_extra_fakturu_partnerovi(faktura)
        if mail_ok:
            faktura.odeslana_emailem = True
            faktura.save(update_fields=['odeslana_emailem'])

    log_superadmin(
        salon,
        user,
        f'Vystavena extra faktura {faktura.cislo_faktury} ({faktura.get_stav_display()}).',
        po={'cislo': faktura.cislo_faktury, 'castka': str(faktura.castka), 'vs': faktura.variabilni_symbol},
    )
    return faktura, mail_ok, mail_detail


def oznacit_extra_uhrazeno(faktura, user, datum=None):
    dnes = datum or timezone.localdate()
    pred_splatnost = faktura.salon.partner_nastaveni.dalsi_splatnost if hasattr(faktura.salon, 'partner_nastaveni') else None
    faktura.stav = ExtraFaktura.STAV_UHRAZENO
    faktura.datum_uhrady = dnes
    faktura.save(update_fields=['stav', 'datum_uhrady'])
    uloz_fakturu_extra(faktura)
    log_superadmin(
        faktura.salon,
        user,
        f'Extra faktura {faktura.cislo_faktury} označena jako uhrazená.',
        po={'cislo': faktura.cislo_faktury},
    )
    return pred_splatnost
