from celery import shared_task


@shared_task(bind=True, max_retries=3, name='flow.email_pristup')
def task_email_flow_pristup(self, flow_user_id, heslo, reset=False):
    from flow.emails import email_flow_pristup_sync
    from flow.models import FlowUser

    user = FlowUser.objects.select_related('salon', 'zamestnanec').get(pk=flow_user_id)
    return email_flow_pristup_sync(user, heslo, reset=reset)


@shared_task(bind=True, max_retries=3, name='flow.email_customer_card_confirm')
def task_email_customer_card_confirm(self, card_id):
    from flow.customer_card_emails import email_customer_card_confirm_sync
    from flow.customer_card_models import CustomerCard

    card = CustomerCard.objects.select_related('salon').get(pk=card_id)
    return email_customer_card_confirm_sync(card)
