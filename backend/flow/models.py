import re
import uuid

from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.utils import timezone

from rezervace.models import Zamestnanec
from salons.models import Salon

HESLO_PATTERN = re.compile(r'^(?=.*[A-Za-z])(?=.*\d).{8,}$')


def heslo_je_platne(raw_password: str) -> bool:
    return bool(raw_password and HESLO_PATTERN.match(raw_password))


class FlowUser(models.Model):
    salon = models.ForeignKey(Salon, related_name='flow_users', on_delete=models.CASCADE)
    zamestnanec = models.OneToOneField(
        Zamestnanec, related_name='flow_ucet', on_delete=models.CASCADE
    )
    email = models.EmailField('e-mail')
    password_hash = models.CharField('heslo (hash)', max_length=128)
    visible_overview = models.BooleanField('Visible Overview', default=False)
    aktivni = models.BooleanField('aktivní', default=True)
    vytvoreno = models.DateTimeField(auto_now_add=True)
    upraveno = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'FLOW účet'
        verbose_name_plural = 'FLOW účty'
        constraints = [
            models.UniqueConstraint(fields=['email'], name='flow_user_email_unique'),
        ]

    def __str__(self):
        return f'{self.email} ({self.salon.name})'

    def set_password(self, raw_password):
        self.password_hash = make_password(raw_password)

    def check_password(self, raw_password):
        if not self.password_hash:
            return False
        return check_password(raw_password, self.password_hash)


class FlowSession(models.Model):
    user = models.ForeignKey(FlowUser, related_name='sessiony', on_delete=models.CASCADE)
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    vytvoreno = models.DateTimeField(auto_now_add=True)
    expirace = models.DateTimeField()

    class Meta:
        verbose_name = 'FLOW session'
        verbose_name_plural = 'FLOW sessiony'

    def je_platna(self):
        return self.user.aktivni and timezone.now() < self.expirace
