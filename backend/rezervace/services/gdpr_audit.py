"""Audit operací souvisejících s GDPR (export, výmaz, účty)."""

from rezervace.services.audit import audit_actor, log_audit


def log_gdpr_audit(request, salon, akce, detail, *, objekt_typ='', objekt_id=None, pred=None, po=None):
    actor = audit_actor(request, salon.pk) if request else 'Systém'
    popis = f'GDPR — {akce}: {detail}'
    log_audit(
        salon=salon,
        kdo=actor,
        kategorie='gdpr',
        popis=popis,
        objekt_typ=objekt_typ,
        objekt_id=objekt_id,
        pred=pred,
        po=po,
    )
