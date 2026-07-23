from django.conf import settings
from django.template.loader import render_to_string

from rezervace.services.emails import _email_via_celery, _odeslat_pro_salon, generate_heslo


def flow_base_url():
    return (getattr(settings, 'FLOW_BASE_URL', None) or 'https://www.ulovklienty.cz/flow/').rstrip('/') + '/'


def email_flow_pristup_sync(flow_user, heslo, reset=False):
    salon = flow_user.salon
    predmet = (
        f'Nové heslo do FLOW – {salon.name}'
        if reset
        else f'Přístup do FLOW – {salon.name}'
    )
    zprava = render_to_string(
        'flow/emails/pristup.txt',
        {
            'flow_user': flow_user,
            'zamestnanec': flow_user.zamestnanec,
            'salon': salon,
            'heslo': heslo,
            'flow_url': flow_base_url(),
            'reset': reset,
        },
    )
    return _odeslat_pro_salon(salon, flow_user.email, predmet, zprava)


def email_flow_pristup(flow_user, heslo, reset=False):
    if _email_via_celery():
        from flow.tasks import task_email_flow_pristup

        task_email_flow_pristup.delay(flow_user.pk, heslo, reset)
        return True
    return email_flow_pristup_sync(flow_user, heslo, reset=reset)


__all__ = ['generate_heslo', 'email_flow_pristup', 'email_flow_pristup_sync', 'flow_base_url']
