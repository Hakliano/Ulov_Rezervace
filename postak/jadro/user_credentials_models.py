from django.conf import settings
from django.db import models


class OdeslaniPrihlasovacich(models.Model):
    """Audit odeslání přístupů — bez hesla."""

    cilovy_uzivatel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='odeslani_prihlasovacich',
    )
    odeslal = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='odeslal_prihlasovacich',
    )
    prijemce = models.EmailField()
    uspech = models.BooleanField(default=False)
    chyba = models.CharField(max_length=300, blank=True, default='')
    vytvoreno = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-vytvoreno']
        verbose_name = 'odeslání přihlašovacích údajů'
        verbose_name_plural = 'odeslání přihlašovacích údajů'
