"""
Životní cyklus rezervace — jeden cron řídí e-maily, anonymizaci i mazání.

Časová osa (stav dokonceno):
  konec služby → +2 h děkovný e-mail → +24 h anonymizace → +12 měsíců smazání
"""

from datetime import timedelta

from django.utils import timezone

from rezervace.models import NoShowZaznam, Rezervace, RezervaceHistorie, SalonAuditLog, ZakaznikSession
from rezervace.notifikace_defaults import (
    cas_odeslani,
    dopln_na_notifikace,
    je_manualni,
    je_v_okne,
    muze_odeslat_notifikaci,
    parse_offset,
)
from rezervace.services.gdpr import (
    ANON_EMAIL_DOMAIN,
    anonymizuj_obsah_rezervace,
    dekujici_notifikace,
    dekujici_notifikace_aktivni,
)
from rezervace.services.emails import ma_kontaktni_email
from rezervace.services.notifikace_email import email_notifikace

DEKUJICI_PO_HODINACH = 2
ANONYMIZACE_PO_HODINACH = 24
DNU_V_MESICI = 30

STAVY_PO_SLUZBE = ('dokonceno', 'no_show', 'zakaznik_storno', 'salon_storno')


def _uchovavani_mesicu_platformy():
    from django.conf import settings
    return getattr(settings, 'GDPR_UCHOVAVANI_MESICU_DEFAULT', 12)


def _uchovavani_dny():
    return _uchovavani_mesicu_platformy() * DNU_V_MESICI


def _je_dekujici_notifikace(notif):
    try:
        return parse_offset(notif['offset']) < 0
    except ValueError:
        return False


def _odeslat_planovane_emaily(now):
    """Připomínky (+24 h) i děkovný e-mail (−2 h po konci)."""
    odeslano = 0
    qs = Rezervace.objects.filter(
        stav__in=('ceka', 'potvrzeno', 'dokonceno', 'no_show'),
        deleted_at__isnull=True,
    ).select_related('salon', 'zamestnanec').prefetch_related('polozky__sluzba')

    for rezervace in qs:
        try:
            nastaveni = rezervace.salon.rezervacni_nastaveni
        except Exception:
            continue

        odeslane = list(rezervace.notifikace_odeslane or [])
        update_fields = []

        for notif in dopln_na_notifikace(nastaveni.notifikace):
            if je_manualni(notif):
                continue
            if not notif.get('aktivni'):
                continue
            nid = str(notif['id'])
            if nid in odeslane:
                continue

            try:
                offset = parse_offset(notif['offset'])
            except ValueError:
                continue
            if not muze_odeslat_notifikaci(rezervace, offset):
                continue

            cilovy = cas_odeslani(rezervace, offset)
            if not je_v_okne(cilovy, now):
                continue

            try:
                if ma_kontaktni_email(rezervace):
                    email_notifikace(rezervace, notif)
                # Bez e-mailu: tiché přeskočení — ne audit chyba, ale označit jako vyřízeno
                # (jinak by děkovný mail blokoval anonymizaci).
                odeslane.append(nid)
                rezervace.notifikace_odeslane = odeslane
                update_fields = ['notifikace_odeslane']

                if _je_dekujici_notifikace(notif) and not rezervace.thank_you_sent_at:
                    rezervace.thank_you_sent_at = now
                    update_fields.append('thank_you_sent_at')

                rezervace.save(update_fields=update_fields)
                if ma_kontaktni_email(rezervace):
                    odeslano += 1
            except Exception:
                pass

    return odeslano


def _zrusit_expirovane_ne_potvrzene(now):
    """Zruší online rezervace, které zákazník nepotvrdil včas."""
    qs = Rezervace.objects.filter(
        stav='ceka',
        typ_vytvoreni='online',
        potvrzeni_exspirace__lt=now,
        deleted_at__isnull=True,
    )
    zruseno = 0
    for rezervace in qs:
        pred = {'stav': rezervace.stav}
        rezervace.stav = 'zakaznik_storno'
        rezervace.save(update_fields=['stav', 'aktualizovano'])
        RezervaceHistorie.objects.create(
            rezervace=rezervace,
            kdo='systém',
            popis='Automatické zrušení – nepotvrzená rezervace',
            data_pred=pred,
            data_po={'stav': rezervace.stav},
        )
        zruseno += 1
    return zruseno


def muze_anonymizovat(rezervace, now):
    """Jednoduché podmínky dle časových razítek na modelu."""
    if rezervace.anonymized_at or rezervace.deleted_at:
        return False
    if rezervace.stav not in STAVY_PO_SLUZBE:
        return False
    if now < rezervace.konec + timedelta(hours=ANONYMIZACE_PO_HODINACH):
        return False
    if rezervace.stav == 'dokonceno' and dekujici_notifikace_aktivni(rezervace):
        if not rezervace.thank_you_sent_at:
            return False
    return True


def _anonymizovat_vhodne(now):
    count = 0
    qs = Rezervace.all_objects.filter(
        anonymized_at__isnull=True,
        deleted_at__isnull=True,
    ).select_related('zakaznik', 'salon')

    for rez in qs:
        if not muze_anonymizovat(rez, now):
            continue
        anonymizuj_obsah_rezervace(rez, now)
        count += 1
    return count


def muze_smazat(rezervace, now):
    if rezervace.deleted_at:
        return False
    if not rezervace.anonymized_at:
        return False
    return now >= rezervace.konec + timedelta(days=_uchovavani_dny())


def _smazat_vyprsale(now):
    """Soft-delete: nastaví deleted_at — rezervace zmizí z kalendáře salonu."""
    count = 0
    qs = Rezervace.all_objects.filter(
        deleted_at__isnull=True,
        anonymized_at__isnull=False,
    ).select_related('salon')
    for rez in qs:
        if not muze_smazat(rez, now):
            continue
        rez.deleted_at = now
        rez.save(update_fields=['deleted_at'])
        count += 1
    return count


def _max_uchovavani_dny():
    return _uchovavani_dny()


def _vycistit_stare_zaznamy(now):
    """Audit log, historie rezervací smazaných po retention období, expirované sessiony."""
    hranice = now - timedelta(days=_max_uchovavani_dny())
    smazano = {'audit': 0, 'historie': 0, 'rezervace': 0, 'noshow': 0, 'sessiony': 0}

    smazano['audit'], _ = SalonAuditLog.objects.filter(kdy__lt=hranice).delete()

    old_deleted_ids = list(
        Rezervace.all_objects.filter(deleted_at__lt=hranice).values_list('id', flat=True),
    )
    if old_deleted_ids:
        smazano['historie'], _ = RezervaceHistorie.objects.filter(
            rezervace_id__in=old_deleted_ids,
        ).delete()
        smazano['noshow'], _ = NoShowZaznam.objects.filter(
            rezervace_id__in=old_deleted_ids,
        ).delete()
        smazano['rezervace'], _ = Rezervace.all_objects.filter(
            id__in=old_deleted_ids,
        ).delete()

    smazano['noshow'] += NoShowZaznam.objects.filter(vytvoreno__lt=hranice).delete()[0]
    smazano['sessiony'], _ = ZakaznikSession.objects.filter(expirace__lt=now).delete()

    return smazano


def proved_zivotni_cyklus(now=None):
    """
    Jediný vstupní bod pro cron.
    ReservationFinished → ThankYouEmail → AnonymizeCustomer → DeleteReservation
    """
    now = now or timezone.now()
    return {
        'emaily_odeslano': _odeslat_planovane_emaily(now),
        'nepotvrzene_zruseno': _zrusit_expirovane_ne_potvrzene(now),
        'anonymizovano': _anonymizovat_vhodne(now),
        'smazano_soft': _smazat_vyprsale(now),
        'vycisteno': _vycistit_stare_zaznamy(now),
    }
