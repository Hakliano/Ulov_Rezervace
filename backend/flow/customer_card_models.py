"""
FLOW – Karta zákazníka (izolovaný modul).

Oddělené tabulky od rezervací. Vazba na rezervace jen přes shodu e-mailu
u aktivní karty (runtime enrichment), bez FK na rezervace.models.Rezervace.
"""
from __future__ import annotations

import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from salons.models import Salon


def generate_confirm_token() -> str:
    return secrets.token_urlsafe(32)


class CustomerCard(models.Model):
    """Zákaznická karta Partnera (tenant = salon)."""

    STAV_CEKA = 'ceka_na_potvrzeni'
    STAV_AKTIVNI = 'aktivni'
    STAV_CHOICES = [
        (STAV_CEKA, 'Čeká na potvrzení'),
        (STAV_AKTIVNI, 'Aktivní'),
    ]

    salon = models.ForeignKey(
        Salon,
        related_name='customer_cards',
        on_delete=models.CASCADE,
    )
    email = models.EmailField('e-mail')
    jmeno = models.CharField('jméno', max_length=120, blank=True, default='')
    telefon = models.CharField('telefon', max_length=40, blank=True, default='')
    poznamka = models.TextField('poznámka o zákazníkovi', blank=True, default='')
    stav = models.CharField(
        max_length=32,
        choices=STAV_CHOICES,
        default=STAV_CEKA,
        db_index=True,
    )

    confirm_token = models.CharField(max_length=64, unique=True, null=True, blank=True)
    confirm_token_expires_at = models.DateTimeField(null=True, blank=True)
    confirm_token_used_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmed_ip = models.GenericIPAddressField(null=True, blank=True)

    vytvoril = models.ForeignKey(
        'flow.FlowUser',
        related_name='customer_cards_vytvorene',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    vytvoreno = models.DateTimeField(auto_now_add=True)
    upraveno = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Zákaznická karta'
        verbose_name_plural = 'Zákaznické karty'
        constraints = [
            models.UniqueConstraint(
                fields=['salon', 'email'],
                name='flow_customer_card_salon_email_uniq',
            ),
        ]
        indexes = [
            models.Index(fields=['salon', 'stav'], name='flow_cc_salon_stav_idx'),
            models.Index(fields=['salon', 'email'], name='flow_cc_salon_email_idx'),
        ]

    def __str__(self):
        return f'{self.email} ({self.salon_id}) [{self.stav}]'

    @property
    def je_aktivni(self) -> bool:
        return self.stav == self.STAV_AKTIVNI

    @property
    def ceka_na_potvrzeni(self) -> bool:
        return self.stav == self.STAV_CEKA

    def issue_confirm_token(self, *, days: int | None = None) -> str:
        days = days if days is not None else int(
            getattr(settings, 'CUSTOMER_CARD_TOKEN_DAYS', 30)
        )
        token = generate_confirm_token()
        self.confirm_token = token
        self.confirm_token_expires_at = timezone.now() + timedelta(days=days)
        self.confirm_token_used_at = None
        return token

    def token_je_platny(self) -> bool:
        if not self.confirm_token or self.confirm_token_used_at:
            return False
        if self.stav != self.STAV_CEKA:
            return False
        if self.confirm_token_expires_at and timezone.now() > self.confirm_token_expires_at:
            return False
        return True


class CustomerVisit(models.Model):
    """Timeline zápis u zákaznické karty (datum + autor + text)."""

    card = models.ForeignKey(
        CustomerCard,
        related_name='visits',
        on_delete=models.CASCADE,
    )
    datum = models.DateField('datum')
    text = models.TextField('záznam')
    autor = models.ForeignKey(
        'flow.FlowUser',
        related_name='customer_visits',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    autor_jmeno = models.CharField('autor (jméno)', max_length=120, blank=True, default='')
    vytvoreno = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Zápis návštěvy'
        verbose_name_plural = 'Zápisy návštěv'
        ordering = ['-datum', '-vytvoreno']

    def __str__(self):
        return f'{self.datum} — {self.card_id}'
