"""Evidence potvrzení seznámení se Zásadami ochrany osobních údajů (informační povinnost)."""

from django.utils import timezone

from rezervace.models import RezervacniNastaveni, SouhlasGDPR
from rezervace.services.client_ip import get_client_ip, get_user_agent

DEFAULT_ZASADY_VERZE = '1.0'


def aktualni_zasady_verze(salon):
    try:
        verze = salon.rezervacni_nastaveni.gdpr_zasady_verze
        return (verze or DEFAULT_ZASADY_VERZE).strip() or DEFAULT_ZASADY_VERZE
    except RezervacniNastaveni.DoesNotExist:
        return DEFAULT_ZASADY_VERZE


def zaloguj_souhlas_gdpr(
    salon,
    typ,
    request,
    *,
    zakaznik=None,
    rezervace=None,
    email='',
    zasady_verze=None,
    jazyk='cs',
):
    """Uloží důkazní záznam potvrzení seznámení se zásadami a aktualizuje zákazníka."""
    verze = (zasady_verze or aktualni_zasady_verze(salon)).strip() or DEFAULT_ZASADY_VERZE
    ip = get_client_ip(request)
    ua = get_user_agent(request)
    now = timezone.now()

    souhlas = SouhlasGDPR.objects.create(
        salon=salon,
        zakaznik=zakaznik,
        rezervace=rezervace,
        email=(email or '').strip().lower(),
        typ=typ,
        zasady_verze=verze,
        jazyk=(jazyk or 'cs')[:10],
        ip_adresa=ip,
        user_agent=ua,
    )

    if zakaznik:
        zakaznik.gdpr_souhlas = True
        zakaznik.gdpr_datum = now
        zakaznik.gdpr_zasady_verze = verze
        if ip:
            zakaznik.gdpr_ip = ip
        zakaznik.save(update_fields=[
            'gdpr_souhlas', 'gdpr_datum', 'gdpr_zasady_verze', 'gdpr_ip',
        ])

    return souhlas
