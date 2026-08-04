from django.template.loader import render_to_string

from flow.customer_card_services import confirm_page_url
from rezervace.services.emails import _email_via_celery, _odeslat_pro_salon, get_email_config


def email_customer_card_confirm_sync(card) -> bool:
    salon = card.salon
    if not card.confirm_token:
        return False
    url = confirm_page_url(card.confirm_token)
    predmet = f'Potvrzení zákaznické karty – {salon.name}'
    ctx = {
        'salon': salon,
        'card': card,
        'confirm_url': url,
    }
    text = render_to_string('flow/emails/customer_card_confirm.txt', ctx)
    html = render_to_string('flow/emails/customer_card_confirm.html', ctx)
    try:
        return bool(_odeslat_pro_salon(salon, card.email, predmet, text, html_body=html))
    except Exception:
        return False


def email_customer_card_confirm(card) -> bool:
    salon = card.salon
    cfg = get_email_config(salon)
    if not cfg.get('smtp_ready'):
        try:
            email_customer_card_confirm_sync(card)
        except Exception:
            pass
        return False
    if _email_via_celery():
        from flow.tasks import task_email_customer_card_confirm

        task_email_customer_card_confirm.delay(card.pk)
        return True
    return email_customer_card_confirm_sync(card)
