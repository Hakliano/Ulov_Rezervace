import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate
from django.db import models
from django.utils import timezone


class PartnerSession(models.Model):
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    expirace = models.DateTimeField()
    vytvoreno = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'partner session'
        verbose_name_plural = 'partner sessions'


def create_partner_session(user, days=7):
    return PartnerSession.objects.create(
        user=user,
        expirace=timezone.now() + timedelta(days=days),
    )


def get_partner_user(request):
    raw = (request.headers.get('X-Partner-Token') or '').strip()
    if not raw:
        return None
    try:
        session = PartnerSession.objects.select_related('user').get(
            token=raw,
            expirace__gt=timezone.now(),
        )
    except (PartnerSession.DoesNotExist, ValueError):
        return None
    user = session.user
    if not user.is_active or not user.is_staff:
        return None
    return user


def partner_login(username, password):
    user = authenticate(username=username, password=password)
    if not user or not user.is_active or not (user.is_staff or user.is_superuser):
        raise ValueError('Neplatné přihlašovací údaje nebo nemáte oprávnění.')
    return create_partner_session(user)
