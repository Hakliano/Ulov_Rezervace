"""Přihlášení personálu — každý zaměstnanec vlastní účet, majitel plný přístup."""

from datetime import timedelta

from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone

from rezervace.models import Zamestnanec, ZamestnanecSession

SESSION_DNY = 14


def normalizuj_prihlasovaci_jmeno(jmeno):
    return (jmeno or '').strip().lower()


def get_staff_from_request(request, salon_id=None):
    token = (request.headers.get('X-Staff-Token') or '').strip()
    if not token:
        return None
    try:
        session = ZamestnanecSession.objects.select_related('zamestnanec').get(
            token=token,
            expirace__gt=timezone.now(),
        )
    except (ZamestnanecSession.DoesNotExist, ValueError):
        return None
    z = session.zamestnanec
    if not z.aktivni and z.role != 'majitel':
        return None
    if salon_id is not None and z.salon_id != int(salon_id):
        return None
    return z


def je_majitel(staff):
    return bool(staff and staff.role == 'majitel')


def staff_do_dict(staff):
    return {
        'id': staff.id,
        'jmeno': staff.jmeno,
        'role': staff.role,
        'prihlasovaci_jmeno': staff.prihlasovaci_jmeno,
        'je_majitel': staff.role == 'majitel',
    }


def prihlasit_staff(salon, prihlasovaci_jmeno, password):
    login = normalizuj_prihlasovaci_jmeno(prihlasovaci_jmeno)
    if not login or not password:
        raise ValueError('Vyplňte přihlašovací jméno a heslo.')

    try:
        staff = Zamestnanec.objects.get(salon=salon, prihlasovaci_jmeno=login)
    except Zamestnanec.DoesNotExist:
        raise ValueError('Nesprávné přihlašovací jméno nebo heslo.')

    if not staff.password_hash:
        raise ValueError('Účet nemá nastavené heslo. Požádejte majitelku salonu.')
    if not staff.check_password(password):
        raise ValueError('Nesprávné přihlašovací jméno nebo heslo.')
    if staff.role != 'majitel' and not staff.aktivni:
        raise ValueError('Váš účet je deaktivován.')

    session = ZamestnanecSession.objects.create(
        zamestnanec=staff,
        expirace=timezone.now() + timedelta(days=SESSION_DNY),
    )
    return session, staff


def odhlasit_staff(token):
    if token:
        ZamestnanecSession.objects.filter(token=token).delete()


def zrusit_vsechny_sessiony(staff):
    ZamestnanecSession.objects.filter(zamestnanec=staff).delete()


def deaktivovat_zamestnance(staff):
    """Účet ponechá v DB kvůli auditu a historii rezervací — jen zablokuje přístup."""
    if staff.role == Zamestnanec.ROLE_MAJITEL:
        raise ValueError('Účet majitelky nelze deaktivovat.')
    staff.aktivni = False
    staff.zobrazit_na_webu = False
    staff.save(update_fields=['aktivni', 'zobrazit_na_webu'])
    zrusit_vsechny_sessiony(staff)
    return staff


def nastav_heslo_staff(staff, raw_password):
    if not raw_password or len(raw_password) < 6:
        raise ValueError('Heslo musí mít alespoň 6 znaků.')
    staff.set_password(raw_password)
    staff.save(update_fields=['password_hash'])


def muze_rezervaci(staff, rezervace):
    """Majitel vidí vše; zaměstnanec jen vlastní rezervace."""
    if not staff:
        return False
    if je_majitel(staff):
        return True
    return rezervace.zamestnanec_id == staff.id
