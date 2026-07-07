"""Salonový audit log — každá administrátorská změna."""

from rezervace.models import SalonAuditLog
from rezervace.services.staff_auth import get_staff_from_request

SENSITIVE_KEYS = frozenset({
    'smtp_password', 'password', 'password_hash', 'heslo', 'token',
})


def audit_actor(request, salon_id=None):
    if not request:
        return 'Systém'
    staff = get_staff_from_request(request, salon_id)
    if staff:
        return staff.jmeno
    name = (request.headers.get('X-Admin-Actor') or '').strip()
    if name:
        return name[:100]
    return 'Administrátor'


def scrub_snapshot(data):
    if data is None:
        return None
    if isinstance(data, dict):
        out = {}
        for k, v in data.items():
            kl = k.lower()
            if kl in SENSITIVE_KEYS or 'password' in kl:
                out[k] = '***'
            else:
                out[k] = scrub_snapshot(v)
        return out
    if isinstance(data, list):
        return [scrub_snapshot(x) for x in data]
    return data


def format_rezervace_ref(rezervace):
    return rezervace.zacatek.strftime('%d.%m.%Y %H:%M')


def log_audit(salon, kdo, kategorie, popis, objekt_typ='', objekt_id=None, pred=None, po=None):
    SalonAuditLog.objects.create(
        salon=salon,
        kdo=(kdo or 'Systém')[:100],
        kategorie=kategorie[:50],
        popis=popis,
        objekt_typ=(objekt_typ or '')[:50],
        objekt_id=objekt_id,
        data_pred=scrub_snapshot(pred),
        data_po=scrub_snapshot(po),
    )


def log_rezervace_audit(rezervace, kdo, popis, pred=None, po=None, request=None):
    actor = audit_actor(request) if request else kdo
    ref = format_rezervace_ref(rezervace)
    log_audit(
        salon=rezervace.salon,
        kdo=actor,
        kategorie='rezervace',
        popis=f'{actor}: {popis} ({ref})',
        objekt_typ='rezervace',
        objekt_id=rezervace.id,
        pred=pred,
        po=po,
    )
