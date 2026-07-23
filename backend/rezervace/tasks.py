"""Celery tasky — odesílání e-mailů na pozadí."""

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


def _retryable(exc):
    """Chybějící záznam nemá smysl opakovat."""
    from django.core.exceptions import ObjectDoesNotExist
    return not isinstance(exc, ObjectDoesNotExist)


def _run(task, fn):
    try:
        return fn()
    except Exception as exc:
        logger.exception('E-mail task %s selhal: %s', task.name, exc)
        if _retryable(exc) and task.request.retries < task.max_retries:
            raise task.retry(exc=exc)
        raise


@shared_task(bind=True, max_retries=3, name='rezervace.email_vyzva_k_potvrzeni')
def task_email_vyzva_k_potvrzeni(self, rezervace_id):
    def _inner():
        from rezervace.models import Rezervace
        from rezervace.services.emails import email_vyzva_k_potvrzeni_sync

        rezervace = Rezervace.objects.get(pk=rezervace_id)
        return email_vyzva_k_potvrzeni_sync(rezervace)

    return _run(self, _inner)


@shared_task(bind=True, max_retries=3, name='rezervace.email_potvrzeni')
def task_email_potvrzeni(self, rezervace_id):
    def _inner():
        from rezervace.models import Rezervace
        from rezervace.services.emails import email_potvrzeni_sync

        rezervace = Rezervace.objects.get(pk=rezervace_id)
        return email_potvrzeni_sync(rezervace)

    return _run(self, _inner)


@shared_task(bind=True, max_retries=3, name='rezervace.email_storno')
def task_email_storno(self, rezervace_id, kdo='zákazník', duvod=''):
    def _inner():
        from rezervace.models import Rezervace
        from rezervace.services.emails import email_storno_sync

        rezervace = Rezervace.objects.get(pk=rezervace_id)
        email_storno_sync(rezervace, kdo=kdo, duvod=duvod)
        return True

    return _run(self, _inner)


@shared_task(bind=True, max_retries=3, name='rezervace.email_nove_heslo')
def task_email_nove_heslo(self, zakaznik_id, heslo):
    def _inner():
        from rezervace.models import Zakaznik
        from rezervace.services.emails import email_nove_heslo_sync

        zakaznik = Zakaznik.objects.get(pk=zakaznik_id)
        return email_nove_heslo_sync(zakaznik, heslo)

    return _run(self, _inner)


@shared_task(bind=True, max_retries=3, name='rezervace.email_notifikace')
def task_email_notifikace(self, rezervace_id, notifikace, extra_ctx=None):
    def _inner():
        from rezervace.models import Rezervace
        from rezervace.services.notifikace_email import email_notifikace_sync

        rezervace = Rezervace.objects.get(pk=rezervace_id)
        return email_notifikace_sync(rezervace, notifikace, extra_ctx=extra_ctx)

    return _run(self, _inner)


@shared_task(bind=True, max_retries=3, name='rezervace.email_platba_qr')
def task_email_platba_qr(self, rezervace_id, notifikace, castka, ucet, variabilni_symbol):
    def _inner():
        from rezervace.models import Rezervace
        from rezervace.services.notifikace_email import email_platba_qr_sync

        rezervace = Rezervace.objects.get(pk=rezervace_id)
        return email_platba_qr_sync(
            rezervace, notifikace, castka, ucet, variabilni_symbol
        )

    return _run(self, _inner)
