from datetime import timedelta

from django.utils import timezone

from flow.models import FlowSession, FlowUser

SESSION_DNY = 30
HEADER = 'X-Flow-Token'


def flow_zam(user):
    """Aktivní persona v requestu (po get_flow_user_from_request), jinak primární Zamestnanec."""
    z = getattr(user, '_persona_zamestnanec', None)
    return z if z is not None else user.zamestnanec


def flow_je_owner(user):
    return flow_zam(user).role == 'majitel'


def flow_ucet_je_majitel(user):
    """Primární účet je majitel (může přepínat na pracovní personu)."""
    primary = getattr(user, '_primary_zamestnanec', None)
    if primary is not None:
        return primary.role == 'majitel'
    return user.zamestnanec.role == 'majitel'


def flow_absence_zam(user):
    """
    Na koho se váže dovolená / absence.
    Manager (admin) nepracuje — absence patří pracovnímu profilu, pokud existuje.
    Běžný Staff = aktivní persona.
    Vrací None, pokud jde o Managera bez pracovní persony (absence nedává smysl).
    """
    if flow_ucet_je_majitel(user):
        pz = getattr(user, 'pracovni_zamestnanec', None)
        if pz is not None:
            return pz
        if user.pracovni_zamestnanec_id:
            return user.pracovni_zamestnanec
        return None
    return flow_zam(user)


def resolve_active_zamestnanec(session):
    user = session.user
    aid = session.active_zamestnanec_id
    if not aid or aid == user.zamestnanec_id:
        return user.zamestnanec
    if user.pracovni_zamestnanec_id and aid == user.pracovni_zamestnanec_id:
        return user.pracovni_zamestnanec
    return user.zamestnanec


def get_flow_session_from_request(request):
    token = (request.headers.get(HEADER) or '').strip()
    if not token:
        return None
    try:
        session = FlowSession.objects.select_related(
            'user',
            'user__salon',
            'user__salon__partner_nastaveni',
            'user__zamestnanec',
            'user__pracovni_zamestnanec',
            'active_zamestnanec',
        ).get(token=token, expirace__gt=timezone.now())
    except (FlowSession.DoesNotExist, ValueError):
        return None
    if not session.user.aktivni:
        return None
    return session


def get_flow_user_from_request(request):
    session = get_flow_session_from_request(request)
    if not session:
        return None
    user = session.user
    primary = user.zamestnanec
    active = resolve_active_zamestnanec(session)
    user._flow_session = session
    user._primary_zamestnanec = primary
    user._persona_zamestnanec = active
    return user


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
        user = FlowUser.objects.select_related(
            'salon', 'salon__partner_nastaveni', 'zamestnanec', 'pracovni_zamestnanec'
        ).get(email__iexact=email_n)
    except FlowUser.DoesNotExist:
        raise ValueError('Nesprávný e-mail nebo heslo.')
    if not user.aktivni:
        raise ValueError('Účet je deaktivován. Kontaktujte majitelku.')
    if not _over_heslo_flow_user(user, password):
        raise ValueError('Nesprávný e-mail nebo heslo.')
    session = FlowSession.objects.create(
        user=user,
        active_zamestnanec=user.zamestnanec,
        expirace=timezone.now() + timedelta(days=SESSION_DNY),
    )
    user._flow_session = session
    user._primary_zamestnanec = user.zamestnanec
    user._persona_zamestnanec = user.zamestnanec
    return session, user


def odhlasit_flow(token):
    if token:
        FlowSession.objects.filter(token=token).delete()


def zrusit_vsechny_sessiony(user):
    FlowSession.objects.filter(user=user).delete()


def prepnout_personu(user, persona: str):
    """
    persona: 'majitel' | 'pracovnik'
    Vyžaduje session na user._flow_session.
    """
    session = getattr(user, '_flow_session', None)
    if not session:
        raise ValueError('Neplatná session.')
    if not flow_ucet_je_majitel(user):
        raise ValueError('Přepínání person je jen pro účet majitelky.')
    persona = (persona or '').strip().lower()
    if persona in ('majitel', 'owner', 'majitelka'):
        session.active_zamestnanec = user.zamestnanec
        session.save(update_fields=['active_zamestnanec'])
        user._persona_zamestnanec = user.zamestnanec
        return 'majitel'
    if persona in ('pracovnik', 'pracovnice', 'staff'):
        pz = user.pracovni_zamestnanec
        if not pz:
            raise ValueError('Pracovní persona ještě není nastavená.')
        if pz.salon_id != user.salon_id:
            raise ValueError('Pracovní persona nepatří k salonu.')
        session.active_zamestnanec = pz
        session.save(update_fields=['active_zamestnanec'])
        user._persona_zamestnanec = pz
        return 'pracovnik'
    raise ValueError('Neplatná persona. Použijte majitel nebo pracovnik.')


def _flow_moduly(user):
    """Jen aktivní moduly — vypnutý Materiálník ve FLOW neexistuje."""
    from partner_admin.services_moduly import materialnik_pro_me

    out = {}
    info = materialnik_pro_me(user.salon)
    if info:
        out['materialnik'] = info
    return out


def web_provozovny_url(domena):
    """Veřejný web partnera. Prázdná doména = žádné tlačítko ve FLOW."""
    host = (domena or '').strip().lower()
    host = host.removeprefix('https://').removeprefix('http://').rstrip('/')
    if not host or '/' in host:
        return ''
    return f'https://{host}'


def _partner_pro_flow(user):
    from django.core.exceptions import ObjectDoesNotExist

    try:
        return user.salon.partner_nastaveni
    except ObjectDoesNotExist:
        return None


def flow_user_do_dict(user):
    active = flow_zam(user)
    primary = getattr(user, '_primary_zamestnanec', None) or user.zamestnanec
    je_owner = active.role == 'majitel'
    ucet_majitel = primary.role == 'majitel'
    pracovni = user.pracovni_zamestnanec
    ceka_volno = 0
    po_splatnosti_dni = 0
    povolit_technicke_nastaveni = False
    nast = _partner_pro_flow(user)
    web_url = web_provozovny_url(nast.domena if nast else '')
    # Badge / splatnost jen když je účet majitelky (i ve staff personě ať vidí alerty)
    if ucet_majitel:
        from rezervace.models import ZamestnanecAbsence
        ceka_volno = ZamestnanecAbsence.objects.filter(
            zamestnanec__salon_id=user.salon_id,
            stav=ZamestnanecAbsence.STAV_CEKA,
        ).count()
        if nast is not None:
            if nast.je_po_splatnosti:
                po_splatnosti_dni = nast.dni_po_splatnosti
            povolit_technicke_nastaveni = bool(nast.povolit_technicke_nastaveni)
    aktivni_kod = 'majitel' if active.id == primary.id else 'pracovnik'
    return {
        'id': user.id,
        'email': user.email,
        'visible_overview': user.visible_overview,
        'aktivni': user.aktivni,
        'ceka_volno_pocet': ceka_volno,
        'po_splatnosti_dni': po_splatnosti_dni,
        'povolit_technicke_nastaveni': povolit_technicke_nastaveni,
        'moduly': _flow_moduly(user),
        'salon': {
            'id': user.salon_id,
            'name': user.salon.name,
            'hero_image': user.salon.hero_image or '',
            'banner_text': user.salon.banner_text or '',
            'banner_od': user.salon.banner_od.isoformat() if user.salon.banner_od else None,
            'banner_do': user.salon.banner_do.isoformat() if user.salon.banner_do else None,
            'banner_enabled': bool(user.salon.banner_enabled),
            'domena': (nast.domena or '').strip() if nast else '',
            'web_url': web_url,
        },
        'zamestnanec': {
            'id': active.id,
            'jmeno': active.jmeno,
            'role': active.role,
            'role_ui': 'owner' if je_owner else 'staff',
            'prihlasovaci_jmeno': active.prihlasovaci_jmeno or '',
            'je_majitel': je_owner,
            'je_owner': je_owner,
        },
        'persona': {
            'aktivni': aktivni_kod,
            'muze_prepinat': bool(ucet_majitel and pracovni_id_ok(user)),
            'majitel': {
                'id': primary.id,
                'jmeno': primary.jmeno,
            },
            'pracovnik': (
                {'id': pracovni.id, 'jmeno': pracovni.jmeno}
                if pracovni_id_ok(user)
                else None
            ),
        },
    }


def pracovni_id_ok(user):
    pz = user.pracovni_zamestnanec
    return bool(pz and pz.salon_id == user.salon_id and pz.aktivni)
