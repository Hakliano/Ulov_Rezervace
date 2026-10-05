"""Centrální entitlement vrstva START / PRO.

PartnerNastaveni.plan určuje funkční oprávnění.
PartnerNastaveni.tarif / PartnerTarif zůstává billing (název, cena, fakturace).

Vyhodnocení:
    partner_ma(salon, feature) = práva plánu ∪ platný grant − platný zákaz

Aktivace modulu (PartnerModul active/inactive) je samostatná věc:
nárok na Archivník/Materiálník ≠ modul zapnutý.
Kartotéka ve FLOW navíc potřebuje aktivní PartnerModul archivnik.

Společný provozní základ (FLOW, Můj den, kalendář, rezervace, SMTP, …)
není v katalogu PRO features — START ho má bez entitlementu.
"""
from __future__ import annotations

from django.utils import timezone

from .models import (
    MODUL_ARCHIVNIK,
    MODUL_MATERIALNIK,
    PartnerFeatureGrant,
    PartnerNastaveni,
)

FEATURE_EXTRA_STAFF = 'extra_staff'
FEATURE_KARTOTEKA = 'kartoteka'
FEATURE_ARCHIVNIK = 'archivnik'
FEATURE_MATERIALNIK = 'materialnik'
FEATURE_IMAP = 'imap'
FEATURE_POST_VISIT_EMAIL = 'post_visit_email'
FEATURE_STATS = 'stats'
FEATURE_AUDIT = 'audit'
FEATURE_TECH_SETTINGS = 'tech_settings'
FEATURE_NOSHOW_ARCHIVE = 'noshow_archive'

FEATURES = {
    FEATURE_EXTRA_STAFF: 'Další personál nad Managerovu pracovní personu',
    FEATURE_KARTOTEKA: 'FLOW Kartotéka (vyžaduje i aktivní Archivník)',
    FEATURE_ARCHIVNIK: 'Nárok na modul Archivník',
    FEATURE_MATERIALNIK: 'Nárok na modul Materiálník',
    FEATURE_IMAP: 'IMAP / příjem pošty',
    FEATURE_POST_VISIT_EMAIL: 'E-mail po návštěvě (záporný offset)',
    FEATURE_STATS: 'Pokročilé statistiky / Přehled',
    FEATURE_AUDIT: 'Audit log',
    FEATURE_TECH_SETTINGS: 'Pokročilé technické nastavení ve FLOW',
    FEATURE_NOSHOW_ARCHIVE: 'NO-SHOW archiv / práce s problémovými zákazníky',
}

PLAN_FEATURES = {
    PartnerNastaveni.PLAN_START: frozenset(),
    PartnerNastaveni.PLAN_PRO: frozenset(FEATURES),
}

MODUL_NA_FEATURE = {
    MODUL_ARCHIVNIK: FEATURE_ARCHIVNIK,
    MODUL_MATERIALNIK: FEATURE_MATERIALNIK,
}


class NeznamaFeature(ValueError):
    """Feature kód není v katalogu. Nové kódy se přidávají do FEATURES."""


class ModulNeniVNaroku(PermissionError):
    """Pokus zapnout modul, na který partner nemá entitlement."""

    def __init__(self, feature, salon=None):
        self.feature = feature
        self.salon = salon
        super().__init__(
            f'Partner nemá nárok na funkci {feature}. '
            f'Aktivace modulu byla odmítnuta.'
        )


def over_feature(feature):
    if feature not in FEATURES:
        raise NeznamaFeature(f'Neznámá feature: {feature}')
    return feature


def _salon(salon):
    if salon is None:
        raise ValueError('salon je povinný')
    if getattr(salon, 'pk', None) is None and not hasattr(salon, 'partner_nastaveni'):
        raise ValueError('salon je povinný')
    return salon


def plan_partnera(salon):
    """Vrátí start|pro. Chybějící / prázdný plán = PRO (stávající provozovny)."""
    salon = _salon(salon)
    try:
        plan = salon.partner_nastaveni.plan
    except PartnerNastaveni.DoesNotExist:
        return PartnerNastaveni.PLAN_PRO
    if plan == PartnerNastaveni.PLAN_START:
        return PartnerNastaveni.PLAN_START
    return PartnerNastaveni.PLAN_PRO


def features_planu(plan):
    if plan == PartnerNastaveni.PLAN_START:
        return PLAN_FEATURES[PartnerNastaveni.PLAN_START]
    return PLAN_FEATURES[PartnerNastaveni.PLAN_PRO]


def _platne_granty(salon, feature, ted):
    qs = PartnerFeatureGrant.objects.filter(
        salon=salon,
        feature=feature,
        aktivni=True,
    )
    vysledek = []
    for grant in qs:
        if grant.je_platny(ted):
            vysledek.append(grant)
    return vysledek


def partner_ma(salon, feature, *, ted=None):
    """True, pokud má partner nárok na feature (plán nebo grant, bez zákazu)."""
    over_feature(feature)
    salon = _salon(salon)
    ted = ted or timezone.now()
    granty = _platne_granty(salon, feature, ted)
    if any(g.zakaz for g in granty):
        return False
    if feature in features_planu(plan_partnera(salon)):
        return True
    if any(not g.zakaz for g in granty):
        return True
    return False


MSG_KARTOTEKA_NEDOSTUPNA = (
    'Kartotéka není pro tuto provozovnu dostupná.'
)
MSG_FUNKCE_NEDOSTUPNA = (
    'Tato funkce není pro tuto provozovnu dostupná.'
)

FLOW_PRO_FEATURE_FLAGS = (
    FEATURE_IMAP,
    FEATURE_POST_VISIT_EMAIL,
    FEATURE_STATS,
    FEATURE_AUDIT,
    FEATURE_TECH_SETTINGS,
    FEATURE_NOSHOW_ARCHIVE,
)


def flow_pro_features_payload(salon, *, ted=None):
    """Flagy pro FLOW /me — UI skryje, backend je autorita."""
    return {
        kod: partner_ma(salon, kod, ted=ted)
        for kod in FLOW_PRO_FEATURE_FLAGS
    }


def kartoteka_smí_fungovat(salon, *, ted=None):
    """Nárok kartoteka + technicky aktivní Archivník. Nezamýká rezervační kontakty."""
    from .services_moduly import archivnik_je_aktivni

    return partner_ma(salon, FEATURE_KARTOTEKA, ted=ted) and archivnik_je_aktivni(salon)


def materialnik_smí_fungovat(salon, *, ted=None):
    """Nárok materialnik + technicky aktivní PartnerModul. Platí i pro START s grantem."""
    from .services_moduly import materialnik_je_aktivni

    return partner_ma(salon, FEATURE_MATERIALNIK, ted=ted) and materialnik_je_aktivni(salon)
