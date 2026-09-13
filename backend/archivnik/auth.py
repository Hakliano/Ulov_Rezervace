"""Přihlášení Archivníku: identita = Zamestnanec, ne FlowUser / FLOW session."""

from datetime import timedelta

from django.utils import timezone

from archivnik.models import ArchivnikSession
from partner_admin.models import MODUL_ARCHIVNIK
from partner_admin.services_moduly import modul_je_aktivni
from rezervace.models import Zamestnanec

HEADER = 'X-Archivnik-Token'
SESSION_DNY = 30


def _normalize_email(value: str) -> str:
    return (value or '').strip().lower()


def authenticate_zamestnanec(email: str, password: str) -> tuple[Zamestnanec | None, str | None]:
    """
    Najde aktivního zaměstnance s heslem. Nevyžaduje FlowUser.
    Vrací (zamestnanec, error_code).
    """
    login = _normalize_email(email)
    if not login or not password:
        return None, 'invalid'
    candidates = list(
        Zamestnanec.objects.select_related('salon').filter(
            aktivni=True,
            prihlasovaci_jmeno__iexact=login,
        ).exclude(prihlasovaci_jmeno='')
    )
    matched = [z for z in candidates if z.check_password(password)]
    if not matched:
        return None, 'invalid'
    enabled = [z for z in matched if modul_je_aktivni(z.salon_id, MODUL_ARCHIVNIK)]
    if not enabled:
        return None, 'module_off'
    return enabled[0], None


def create_session(zamestnanec: Zamestnanec) -> ArchivnikSession:
    return ArchivnikSession.objects.create(
        zamestnanec=zamestnanec,
        expirace=timezone.now() + timedelta(days=SESSION_DNY),
    )


def get_session_from_request(request) -> ArchivnikSession | None:
    raw = (request.headers.get(HEADER) or '').strip()
    if not raw:
        return None
    try:
        session = ArchivnikSession.objects.select_related(
            'zamestnanec',
            'zamestnanec__salon',
            'zamestnanec__salon__partner_nastaveni',
        ).get(token=raw)
    except (ArchivnikSession.DoesNotExist, ValueError):
        return None
    if not session.je_platna():
        return None
    if not modul_je_aktivni(session.zamestnanec.salon_id, MODUL_ARCHIVNIK):
        return None
    return session


def get_actor_from_request(request) -> Zamestnanec | None:
    session = get_session_from_request(request)
    return session.zamestnanec if session else None
