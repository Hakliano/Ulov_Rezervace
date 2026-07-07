"""GDPR — hash e-mailů a anonymizace obsahu rezervace."""

import hashlib
from datetime import timedelta

from django.utils import timezone

from rezervace.models import NoShowZaznam, Zakaznik, ZakaznikSession
from rezervace.notifikace_defaults import (
    dopln_na_notifikace,
    je_manualni,
    parse_offset,
)

ANONYMIZACE_PO_HODINACH = 24
UCHOVAVANI_MESICU = 12
ANON_EMAIL_DOMAIN = 'anonym.ulovrezervaci.local'


def email_hash(email):
    e = (email or '').strip().lower()
    if not e or '@' not in e:
        return ''
    return hashlib.sha256(e.encode('utf-8')).hexdigest()


def anon_email_placeholder(obj_id):
    return f'anon-{obj_id}@{ANON_EMAIL_DOMAIN}'


def dekujici_notifikace(rezervace):
    try:
        nastaveni = rezervace.salon.rezervacni_nastaveni
    except Exception:
        return None
    items = dopln_na_notifikace(nastaveni.notifikace)
    for notif in items:
        if je_manualni(notif):
            continue
        if not notif.get('aktivni'):
            continue
        try:
            if parse_offset(notif['offset']) < 0:
                return notif
        except ValueError:
            continue
    return None


def dekujici_notifikace_aktivni(rezervace):
    """True pokud je děkovný e-mail zapnutý (thank_you_enabled)."""
    return dekujici_notifikace(rezervace) is not None


def _scrub_historie(rezervace):
    for h in rezervace.historie.all():
        changed = False
        for field in ('data_pred', 'data_po'):
            data = getattr(h, field)
            if not isinstance(data, dict):
                continue
            for key in list(data.keys()):
                if 'email' in key.lower():
                    data[key] = ''
                    changed = True
            if changed:
                setattr(h, field, data)
        if changed:
            h.save(update_fields=['data_pred', 'data_po'])


def anonymizuj_obsah_rezervace(rezervace, now=None):
    """Vymaže osobní údaje a nastaví anonymized_at."""
    now = now or timezone.now()

    rezervace.email_host = ''
    rezervace.poznamka_zakaznika = ''
    rezervace.anonymized_at = now
    rezervace.save(update_fields=['email_host', 'poznamka_zakaznika', 'anonymized_at'])

    if rezervace.zakaznik_id:
        z = rezervace.zakaznik
        if z.email and not z.email.endswith(f'@{ANON_EMAIL_DOMAIN}'):
            if not z.email_hash:
                z.email_hash = email_hash(z.email)
            z.email = anon_email_placeholder(z.id)
            z.password_hash = ''
            z.marketing_souhlas = False
            z.save(update_fields=['email', 'email_hash', 'password_hash', 'marketing_souhlas'])
            ZakaznikSession.objects.filter(zakaznik=z).delete()

    for ns in NoShowZaznam.objects.filter(rezervace=rezervace):
        if ns.email and not ns.email_hash:
            ns.email_hash = email_hash(ns.email)
        ns.email = ''
        ns.save(update_fields=['email', 'email_hash'])

    _scrub_historie(rezervace)
    return True
