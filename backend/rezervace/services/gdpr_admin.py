"""Export a výmaz osobních údajů na žádost (administrátor salonu)."""

from django.utils import timezone

from rezervace.models import Rezervace, SouhlasGDPR, Zakaznik, ZakaznikSession
from rezervace.serializers import RezervaceSerializer
from rezervace.services.gdpr import anonymizuj_obsah_rezervace, email_hash


def export_zakaznik_data(zakaznik):
    rezervace = Rezervace.all_objects.filter(zakaznik=zakaznik).order_by('-zacatek')
    souhlasy = SouhlasGDPR.objects.filter(zakaznik=zakaznik).order_by('-vytvoreno')
    return {
        'exportovano': timezone.now().isoformat(),
        'zakaznik': {
            'id': zakaznik.id,
            'nick': zakaznik.nick,
            'email': zakaznik.email,
            'potvrzeni_seznameni_se_zasadami': zakaznik.gdpr_souhlas,
            'datum_potvrzeni_zasad': zakaznik.gdpr_datum.isoformat() if zakaznik.gdpr_datum else None,
            'verze_zasad': zakaznik.gdpr_zasady_verze,
            'ip_pri_potvrzeni': str(zakaznik.gdpr_ip) if zakaznik.gdpr_ip else None,
            'blokovan': zakaznik.blokovan,
            'no_show_pocet': zakaznik.no_show_pocet,
            'vytvoreno': zakaznik.vytvoreno.isoformat(),
        },
        'rezervace': RezervaceSerializer(rezervace, many=True).data,
        'evidence_informacni_povinnosti': [
            {
                'typ': s.typ,
                'zasady_verze': s.zasady_verze,
                'jazyk': s.jazyk,
                'ip_adresa': str(s.ip_adresa) if s.ip_adresa else None,
                'vytvoreno': s.vytvoreno.isoformat(),
                'rezervace_id': s.rezervace_id,
            }
            for s in souhlasy
        ],
    }


def vymaz_zakaznik_na_zadost(zakaznik, now=None):
    """
    Výmaz / anonymizace všech osobních údajů zákazníka v salonu.
    Rezervace zůstanou anonymizované pro statistiky do konce retention období.
    """
    now = now or timezone.now()
    email_pred = zakaznik.email
    pred = {'email': email_pred, 'nick': zakaznik.nick}

    for rez in Rezervace.all_objects.filter(zakaznik=zakaznik):
        if not rez.anonymized_at:
            anonymizuj_obsah_rezervace(rez, now)

    ZakaznikSession.objects.filter(zakaznik=zakaznik).delete()

    eh = email_hash(email_pred) if email_pred else zakaznik.email_hash
    zakaznik.email = f'vymazano-{zakaznik.id}@vymazano.local'
    zakaznik.nick = f'Vymazáno #{zakaznik.id}'
    zakaznik.email_hash = eh or zakaznik.email_hash
    zakaznik.password_hash = ''
    zakaznik.gdpr_souhlas = False
    zakaznik.gdpr_ip = None
    zakaznik.blokovan = True
    zakaznik.save(update_fields=[
        'email', 'nick', 'email_hash', 'password_hash',
        'gdpr_souhlas', 'gdpr_ip', 'blokovan',
    ])

    po = {'email': zakaznik.email, 'stav': 'vymazano_na_zadost'}
    return pred, po
