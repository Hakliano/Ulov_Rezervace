from celery import shared_task


@shared_task(bind=True, max_retries=3, name='flow.email_pristup')
def task_email_flow_pristup(self, flow_user_id, heslo, reset=False):
    from flow.emails import email_flow_pristup_sync
    from flow.models import FlowUser

    user = FlowUser.objects.select_related('salon', 'zamestnanec').get(pk=flow_user_id)
    return email_flow_pristup_sync(user, heslo, reset=reset)
