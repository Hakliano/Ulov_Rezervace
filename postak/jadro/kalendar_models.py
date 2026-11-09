from django.conf import settings
from django.db import models


class KalendarUdalost(models.Model):
    TYP_SCHUZKA = 'schuzka'
    TYP_TELEFONAT = 'telefonat'
    TYP_UKOL = 'ukol'
    TYP_OSTATNI = 'ostatni'
    TYPY = [
        (TYP_SCHUZKA, 'Schůzka'),
        (TYP_TELEFONAT, 'Telefonát'),
        (TYP_UKOL, 'Úkol'),
        (TYP_OSTATNI, 'Ostatní'),
    ]

    nazev = models.CharField(max_length=200)
    zacatek = models.DateTimeField(db_index=True)
    konec = models.DateTimeField()
    typ = models.CharField(max_length=16, choices=TYPY, db_index=True)
    popis = models.TextField(blank=True, default='')
    prirazeny = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='kalendar_udalosti',
    )
    vytvoril = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='kalendar_vytvorene',
    )
    klient_modernik = models.ForeignKey(
        'jadro.KlientModernik',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='kalendar_udalosti',
    )
    klient_hya = models.ForeignKey(
        'jadro.KlientHya',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='kalendar_udalosti',
    )
    hotovo = models.BooleanField(default=False)
    vytvoreno = models.DateTimeField(auto_now_add=True)
    upraveno = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['zacatek', 'id']
        indexes = [
            models.Index(fields=['prirazeny', 'zacatek']),
            models.Index(fields=['typ', 'hotovo']),
        ]

    def je_po_terminu(self, now=None):
        from django.utils import timezone

        now = now or timezone.now()
        return self.typ == self.TYP_UKOL and not self.hotovo and self.konec < now
