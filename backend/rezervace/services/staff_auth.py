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
    from flow.models import FlowUser

    je_owner = staff.role == 'majitel'
    email = ''
    try:
        email = staff.flow_ucet.email or ''
    except FlowUser.DoesNotExist:
        email = ''
    if not email and staff.prihlasovaci_jmeno and '@' in staff.prihlasovaci_jmeno:
        email = staff.prihlasovaci_jmeno
    return {
        'id': staff.id,
        'jmeno': staff.jmeno,
        # DB hodnoty zůstávají majitel/zamestnanec; owner/staff = produktové aliasy
        'role': staff.role,
        'role_ui': 'owner' if je_owner else 'staff',
        'email': email,
        'prihlasovaci_jmeno': staff.prihlasovaci_jmeno,
        'je_majitel': je_owner,
        'je_owner': je_owner,
    }


def _je_email(hodnota):
    v = (hodnota or '').strip()
    return '@' in v and '.' in v.split('@')[-1]


def najdi_staff_pro_login(salon, login):
    """Login je e-mail. Owner i staff: FlowUser.email, fallback prihlasovaci_jmeno=email."""
    from flow.models import FlowUser

    email = normalizuj_prihlasovaci_jmeno(login)
    if not email:
        return None
    if not _je_email(email):
        raise ValueError('Přihlášení je pouze e-mailem.')

    try:
        flow = FlowUser.objects.select_related('zamestnanec').get(
            email__iexact=email,
            salon=salon,
        )
        return flow.zamestnanec
    except FlowUser.DoesNotExist:
        pass

    try:
        return Zamestnanec.objects.get(salon=salon, prihlasovaci_jmeno=email)
    except Zamestnanec.DoesNotExist:
        return None


def sync_owner_login_email(staff, email):
    """E-mail majitele = globálně unikátní login (FlowUser + prihlasovaci_jmeno)."""
    from flow.models import FlowUser

    if not je_majitel(staff):
        return
    email_n = normalizuj_prihlasovaci_jmeno(email)
    if not _je_email(email_n):
        raise ValueError('E-mail majitele není platný.')

    konflikt_flow = FlowUser.objects.filter(email__iexact=email_n).exclude(
        zamestnanec_id=staff.id
    )
    if konflikt_flow.exists():
        raise ValueError('Tento e-mail už používá jiný účet. Každý salon musí mít jiný e-mail majitele.')

    konflikt_staff = Zamestnanec.objects.filter(
        prihlasovaci_jmeno=email_n,
    ).exclude(pk=staff.pk)
    if konflikt_staff.exists():
        raise ValueError('Tento e-mail už používá jiný účet. Každý salon musí mít jiný e-mail majitele.')

    if staff.prihlasovaci_jmeno != email_n:
        staff.prihlasovaci_jmeno = email_n
        staff.save(update_fields=['prihlasovaci_jmeno'])


def prihlasit_staff(salon, prihlasovaci_jmeno, password):
    login = normalizuj_prihlasovaci_jmeno(prihlasovaci_jmeno)
    if not login or not password:
        raise ValueError('Vyplňte e-mail a heslo.')

    try:
        staff = najdi_staff_pro_login(salon, login)
    except ValueError:
        raise
    if staff is None:
        raise ValueError('Nesprávný e-mail nebo heslo.')

    if not staff.password_hash:
        raise ValueError('Účet nemá nastavené heslo. Požádejte majitelku salonu.')
    if not staff.check_password(password):
        raise ValueError('Nesprávný e-mail nebo heslo.')
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
    if je_majitel(staff):
        sync_owner_heslo_do_flow(staff, raw_password)


def sync_owner_heslo_do_flow(staff, raw_password):
    """Sdílené heslo ownera: Zamestnanec je zdroj pravdy, FlowUser se drží v synci."""
    if not je_majitel(staff) or not raw_password:
        return
    from flow.models import FlowUser

    try:
        flow_ucet = staff.flow_ucet
    except FlowUser.DoesNotExist:
        return
    flow_ucet.set_password(raw_password)
    flow_ucet.save(update_fields=['password_hash', 'upraveno'])


def ensure_owner_flow_user(salon, email=None):
    """
    Zajistí FLOW účet majitele (I7: Přejít do FLOW).
    Idempotentní. Heslo = stejný hash jako web-admin.
    Vrací (flow_user, created: bool).
    """
    from flow.models import FlowUser

    majitel = (
        Zamestnanec.objects.filter(salon=salon, role=Zamestnanec.ROLE_MAJITEL)
        .order_by('id')
        .first()
    )
    if not majitel:
        raise ValueError('Salon nemá účet majitele.')
    if not majitel.password_hash:
        raise ValueError('Majitel nemá nastavené heslo. Nejdřív nastavte heslo.')

    # Hint z UI může být neplatný nebo kontakt webu (sdílený napříč demy) —
    # login majitele má přednost.
    email_n = normalizuj_prihlasovaci_jmeno(email) if email else ''
    if email_n and not _je_email(email_n):
        email_n = ''

    def _fallback_owner_email():
        if _je_email(majitel.prihlasovaci_jmeno):
            return normalizuj_prihlasovaci_jmeno(majitel.prihlasovaci_jmeno)
        try:
            fe = normalizuj_prihlasovaci_jmeno(majitel.flow_ucet.email)
            if _je_email(fe):
                return fe
        except FlowUser.DoesNotExist:
            pass
        # salon.email jen když není konflikt s jiným účtem
        salon_email = normalizuj_prihlasovaci_jmeno(getattr(salon, 'email', '') or '')
        if _je_email(salon_email):
            taken = FlowUser.objects.filter(email__iexact=salon_email).exclude(
                zamestnanec_id=majitel.id
            ).exists()
            if not taken:
                return salon_email
        return ''

    if not email_n:
        email_n = _fallback_owner_email()
    elif FlowUser.objects.filter(email__iexact=email_n).exclude(zamestnanec_id=majitel.id).exists():
        # např. info@ulovklienty.cz z kontaktu webu = login jiného dema
        email_n = _fallback_owner_email()

    if not _je_email(email_n):
        raise ValueError(
            'E-mail majitele není platný. Nastavte unikátní e-mail přihlášení majitele '
            '(ne kontaktní e-mail na webu).'
        )

    try:
        flow_ucet = majitel.flow_ucet
    except FlowUser.DoesNotExist:
        flow_ucet = None

    if flow_ucet is not None:
        sync_owner_login_email(majitel, email_n)
        if flow_ucet.email != email_n:
            flow_ucet.email = email_n
            flow_ucet.save(update_fields=['email', 'upraveno'])
        if majitel.password_hash and flow_ucet.password_hash != majitel.password_hash:
            flow_ucet.password_hash = majitel.password_hash
            flow_ucet.save(update_fields=['password_hash', 'upraveno'])
        return flow_ucet, False

    sync_owner_login_email(majitel, email_n)
    if FlowUser.objects.filter(email__iexact=email_n).exclude(zamestnanec_id=majitel.id).exists():
        raise ValueError('Tento e-mail už je použit u jiného FLOW účtu.')

    flow_ucet = FlowUser(
        salon=salon,
        zamestnanec=majitel,
        email=email_n,
        visible_overview=True,
        aktivni=True,
        password_hash=majitel.password_hash,
    )
    flow_ucet.save()
    return flow_ucet, True


def owner_flow_stav(salon):
    """Stav aktivace FLOW pro majitele (web-admin / partner-admin)."""
    from flow.models import FlowUser

    majitel = (
        Zamestnanec.objects.filter(salon=salon, role=Zamestnanec.ROLE_MAJITEL)
        .order_by('id')
        .first()
    )
    if not majitel:
        return {
            'ma_majitele': False,
            'aktivni': False,
            'email': '',
            'ma_heslo': False,
        }
    email = ''
    aktivni = False
    try:
        fu = majitel.flow_ucet
        email = fu.email or ''
        aktivni = True
    except FlowUser.DoesNotExist:
        if _je_email(majitel.prihlasovaci_jmeno):
            email = majitel.prihlasovaci_jmeno
        elif _je_email(getattr(salon, 'email', '') or ''):
            email = salon.email
    return {
        'ma_majitele': True,
        'aktivni': aktivni,
        'email': email,
        'ma_heslo': bool(majitel.password_hash),
        'majitel_id': majitel.id,
        'majitel_jmeno': majitel.jmeno,
    }


def zmen_sdilene_heslo_owner(staff, current_password, new_password):
    """Owner mění sdílené heslo (web-admin + FLOW). Staff self-change sem nepatří."""
    from flow.models import heslo_je_platne

    if not je_majitel(staff):
        raise ValueError('Sdílené heslo může měnit jen majitel salonu.')
    if not staff.check_password(current_password):
        raise ValueError('Současné heslo nesedí.')
    if not heslo_je_platne(new_password):
        raise ValueError('Nové heslo musí mít alespoň 8 znaků, jedno písmeno a jedno číslo.')
    if current_password == new_password:
        raise ValueError('Nové heslo musí být jiné než současné.')
    staff.set_password(new_password)
    staff.save(update_fields=['password_hash'])
    sync_owner_heslo_do_flow(staff, new_password)
    return staff


def muze_rezervaci(staff, rezervace):
    """Majitel vidí vše; zaměstnanec jen vlastní rezervace."""
    if not staff:
        return False
    if je_majitel(staff):
        return True
    return rezervace.zamestnanec_id == staff.id
