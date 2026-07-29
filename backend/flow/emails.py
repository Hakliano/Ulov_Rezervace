from django.conf import settings
from django.template.loader import render_to_string

from rezervace.services.emails import (
    _email_via_celery,
    _odeslat_pro_salon,
    generate_heslo,
    get_email_config,
)


def flow_base_url():
    return (getattr(settings, 'FLOW_BASE_URL', None) or 'https://www.ulovklienty.cz/flow/').rstrip('/') + '/'


def smtp_opravdu_odesila(salon):
    """True jen při reálném SMTP — ne Local console a ne salon bez SMTP hesla."""
    if 'console' in (getattr(settings, 'EMAIL_BACKEND', '') or '').lower():
        return False
    return bool(get_email_config(salon).get('smtp_ready'))


def email_flow_pristup_sync(flow_user, heslo, reset=False):
    salon = flow_user.salon
    predmet = (
        f'Nové heslo do FLOW CRM – {salon.name}'
        if reset
        else f'Přístup do FLOW CRM – {salon.name}'
    )
    ctx = {
        'flow_user': flow_user,
        'zamestnanec': flow_user.zamestnanec,
        'salon': salon,
        'heslo': heslo,
        'flow_url': flow_base_url(),
        'reset': reset,
    }
    zprava = render_to_string('flow/emails/pristup.txt', ctx)
    html = render_to_string('flow/emails/pristup.html', ctx)
    try:
        return bool(_odeslat_pro_salon(salon, flow_user.email, predmet, zprava, html_body=html))
    except Exception:
        # Účet / heslo už může být uložené — nesmí spadnout celý request na 500
        return False


def email_flow_pristup(flow_user, heslo, reset=False):
    """
    Vrátí True jen když má smysl věřit, že mail dojde (reálné SMTP).
    Na Local / bez SMTP se heslo vypíše do konzole (dev), ale vrátí False —
    majitelka musí dostat heslo v API odpovědi.
    """
    salon = flow_user.salon
    if not smtp_opravdu_odesila(salon):
        try:
            email_flow_pristup_sync(flow_user, heslo, reset=reset)
        except Exception:
            pass
        return False
    if _email_via_celery():
        from flow.tasks import task_email_flow_pristup

        task_email_flow_pristup.delay(flow_user.pk, heslo, reset)
        return True
    return email_flow_pristup_sync(flow_user, heslo, reset=reset)


def flow_pristup_payload(heslo, email_ok, *, reset=False):
    """Jednotná odpověď pro create/reset FLOW hesla."""
    if email_ok:
        return {
            'email_odeslan': True,
            'detail': (
                'Nové heslo odesláno e-mailem.'
                if reset
                else 'Přístup vytvořen. Dočasné heslo bylo odesláno e-mailem.'
            ),
        }
    return {
        'email_odeslan': False,
        'docasne_heslo': heslo,
        'detail': (
            f'Heslo připraveno (e-mail se neodeslal — Local/bez SMTP). Zkopírujte: {heslo}'
            if reset
            else f'Přístup vytvořen (e-mail se neodeslal — Local/bez SMTP). Heslo: {heslo}'
        ),
    }


__all__ = [
    'generate_heslo',
    'email_flow_pristup',
    'email_flow_pristup_sync',
    'flow_base_url',
    'smtp_opravdu_odesila',
    'flow_pristup_payload',
]
