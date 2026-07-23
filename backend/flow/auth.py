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


def prihlasit_flow(email, password):
    email_n = (email or '').strip().lower()
    if not email_n or not password:
        raise ValueError('Vyplňte e-mail a heslo.')
    try:
        user = FlowUser.objects.select_related('salon', 'zamestnanec').get(email__iexact=email_n)
    except FlowUser.DoesNotExist:
        raise ValueError('Nesprávný e-mail nebo heslo.')
    if not user.aktivni:
        raise ValueError('Účet je deaktivován. Kontaktujte majitelku.')
    if not user.check_password(password):
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
    return {
        'id': user.id,
        'email': user.email,
        'visible_overview': user.visible_overview,
        'aktivni': user.aktivni,
        'salon': {
            'id': user.salon_id,
            'name': user.salon.name,
            'hero_image': user.salon.hero_image or '',
        },
        'zamestnanec': {
            'id': user.zamestnanec_id,
            'jmeno': user.zamestnanec.jmeno,
            'role': user.zamestnanec.role,
        },
    }
