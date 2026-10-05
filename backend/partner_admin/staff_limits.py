"""Personální limity START nad entitlement extra_staff.

Pracovní persona Managera (FlowUser.pracovni_zamestnanec) není extra staff.
Aktivní extra personál = role=zamestnanec, aktivni=True, mimo tuto personu.
"""
from __future__ import annotations

from partner_admin.entitlements import FEATURE_EXTRA_STAFF, partner_ma, plan_partnera
from partner_admin.models import PartnerNastaveni
from rezervace.models import Zamestnanec

MSG_EXTRA_STAFF = (
    'Tarif START neumožňuje další pracovníky. '
    'Pracovní persona Managera není extra personál — tu spravujete v „Manager také pracuje“.'
)
MSG_MANAGER_POVINNY = (
    'U tarifu START musí Manager pracovat. Pracovní personu nelze vypnout.'
)
MSG_PLAN_START = (
    'Partnera nelze převést na START, protože má další aktivní pracovníky. '
    'Nejdříve vyřešte personál a jeho budoucí rezervace.'
)


class ExtraStaffNeniVNaroku(ValueError):
    pass


class StartManagerPracujePovinny(ValueError):
    pass


def ma_extra_staff(salon) -> bool:
    return partner_ma(salon, FEATURE_EXTRA_STAFF)


def manager_pracuje_povinny(salon) -> bool:
    return not ma_extra_staff(salon)


def staff_entitlements_payload(salon) -> dict:
    extra = ma_extra_staff(salon)
    return {
        'extra_staff': extra,
        'plan': plan_partnera(salon),
        'manager_pracuje_povinny': not extra,
    }


def pracovni_persona_managera(salon) -> Zamestnanec | None:
    from flow.models import FlowUser

    fu = (
        FlowUser.objects.filter(salon=salon, zamestnanec__role=Zamestnanec.ROLE_MAJITEL)
        .select_related('pracovni_zamestnanec')
        .first()
    )
    if not fu:
        return None
    pz = fu.pracovni_zamestnanec
    if not pz or pz.salon_id != getattr(salon, 'pk', None):
        return None
    return pz


def je_pracovni_persona_managera(salon, zamestnanec) -> bool:
    if zamestnanec is None:
        return False
    pz = pracovni_persona_managera(salon)
    return bool(pz and pz.pk == getattr(zamestnanec, 'pk', None))


def aktivni_extra_staff_qs(salon):
    """Aktivní provozní personál mimo pracovní personu Managera.

    Poznává se podle Zamestnanec.aktivni=True (stejný příznak jako dostupnost
    a deaktivace). Historický pracovník má aktivni=False a START neblokuje.
    zobrazit_na_webu na bookovatelnost ani na tento počet nemá vliv.
    """
    qs = Zamestnanec.objects.filter(
        salon=salon,
        role=Zamestnanec.ROLE_ZAMESTNANEC,
        aktivni=True,
    )
    pz = pracovni_persona_managera(salon)
    if pz is not None:
        qs = qs.exclude(pk=pz.pk)
    return qs


def extra_staff_brani_startu(salon) -> bool:
    return aktivni_extra_staff_qs(salon).exists()


def over_vytvoreni_extra_staff(salon):
    if not ma_extra_staff(salon):
        raise ExtraStaffNeniVNaroku(MSG_EXTRA_STAFF)


def over_reaktivaci_extra_staff(salon, zamestnanec):
    if je_pracovni_persona_managera(salon, zamestnanec):
        return
    over_vytvoreni_extra_staff(salon)


def over_vypnuti_manager_pracuje(salon):
    if manager_pracuje_povinny(salon):
        raise StartManagerPracujePovinny(MSG_MANAGER_POVINNY)


def over_deaktivaci_zamestnance(salon, zamestnanec):
    if je_pracovni_persona_managera(salon, zamestnanec):
        over_vypnuti_manager_pracuje(salon)


def over_plan_start(salon, plan):
    if plan != PartnerNastaveni.PLAN_START:
        return
    if extra_staff_brani_startu(salon):
        from django.core.exceptions import ValidationError

        raise ValidationError({'plan': MSG_PLAN_START})


def zajisti_manager_pracuje_pro_start(salon):
    """START musí mít aktivní pracovní personu. Nic nemaže, jen zapne/obnoví."""
    if not manager_pracuje_povinny(salon):
        return None
    majitel = Zamestnanec.objects.filter(
        salon=salon, role=Zamestnanec.ROLE_MAJITEL,
    ).first()
    if not majitel or not majitel.password_hash:
        return None
    from flow.persona_service import set_majitelka_pracuje

    return set_majitelka_pracuje(salon, ano=True)
