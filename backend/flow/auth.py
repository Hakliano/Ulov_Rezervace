from datetime import timedelta

from django.utils import timezone

from flow.models import FlowSession, FlowUser

SESSION_DNY = 30
HEADER = 'X-Flow-Token'


def get_flow_user_from_request(request):
    token = (request.headers.get(HEADER) or '').strip()
    if not token:
        return None
    try:
        session = FlowSession.objects.select_related(
            'user', 'user__salon', 'user__zamestnanec'
        ).get(token=token, expirace__gt=timezone.now())
    except (FlowSession.DoesNotExist, ValueError):
        return None
    if not session.user.aktivni:
        return None
    return session.user


def _over_heslo_flow_user(user, password):
    """Owner: heslo ze Zamestnanec (sdílené). Staff: heslo z FlowUser."""
    zam = user.zamestnanec
    if zam.role == 'majitel':
        if not zam.password_hash or not zam.check_password(password):
            return False
        # Drží FlowUser hash v synci po starších datech / migracích.
        if not user.check_password(password):
            user.set_password(password)
            user.save(update_fields=['password_hash', 'upraveno'])
        return True
    return user.check_password(password)


def prihlasit_flow(email, password):
    """Přihlášení jen e-mailem (globálně unikátní). Heslo ownera je sdílené se Zamestnanec."""
    email_n = (email or '').strip().lower()
    if not email_n or not password:
        raise ValueError('Vyplňte e-mail a heslo.')
    if '@' not in email_n:
        raise ValueError('Přihlášení je pouze e-mailem.')
    try:
        user = FlowUser.objects.select_related('salon', 'zamestnanec').get(
            email__iexact=email_n
        )
    except FlowUser.DoesNotExist:
        raise ValueError('Nesprávný e-mail nebo heslo.')
    if not user.aktivni:
        raise ValueError('Účet je deaktivován. Kontaktujte majitelku.')
    if not _over_heslo_flow_user(user, password):
        raise ValueError('Nesprávný e-mail nebo heslo.')
    session = FlowSession.objects.create(
        user=user,
        expirace=timezone.now() + timedelta(days=SESSION_DNY),
    )
    return session, user


def odhlasit_flow(token):
    if token:
        FlowSession.objects.filter(token=token).delete()


def zrusit_vsechny_sessiony(user):
    FlowSession.objects.filter(user=user).delete()


def flow_user_do_dict(user):
    je_owner = user.zamestnanec.role == 'majitel'
    ceka_volno = 0
    po_splatnosti_dni = 0
    if je_owner:
        from partner_admin.models import PartnerNastaveni
        from rezervace.models import ZamestnanecAbsence
        ceka_volno = ZamestnanecAbsence.objects.filter(
            zamestnanec__salon_id=user.salon_id,
            stav=ZamestnanecAbsence.STAV_CEKA,
        ).count()
        try:
            nast = PartnerNastaveni.objects.get(salon_id=user.salon_id)
            if nast.je_po_splatnosti:
                po_splatnosti_dni = nast.dni_po_splatnosti
        except PartnerNastaveni.DoesNotExist:
            po_splatnosti_dni = 0
    return {
        'id': user.id,
        'email': user.email,
        'visible_overview': user.visible_overview,
        'aktivni': user.aktivni,
        'ceka_volno_pocet': ceka_volno,
        'po_splatnosti_dni': po_splatnosti_dni,
        'salon': {
            'id': user.salon_id,
            'name': user.salon.name,
            'hero_image': user.salon.hero_image or '',
            'banner_text': user.salon.banner_text or '',
            'banner_od': user.salon.banner_od.isoformat() if user.salon.banner_od else None,
            'banner_do': user.salon.banner_do.isoformat() if user.salon.banner_do else None,
            'banner_enabled': bool(user.salon.banner_enabled),
        },
        'zamestnanec': {
            'id': user.zamestnanec_id,
            'jmeno': user.zamestnanec.jmeno,
            'role': user.zamestnanec.role,
            'role_ui': 'owner' if je_owner else 'staff',
            'prihlasovaci_jmeno': user.zamestnanec.prihlasovaci_jmeno or '',
            'je_majitel': je_owner,
            'je_owner': je_owner,
        },
    }
