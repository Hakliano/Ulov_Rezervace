from django.conf import settings
from django.db import models

REZIM_SDILENE = 'sdilene'
REZIM_MOJE = 'moje'
REZIMY = (
    (REZIM_SDILENE, 'Sdílené dokumenty'),
    (REZIM_MOJE, 'Moje dokumenty'),
)


def _upload_path(instance, _filename):
    rezim = instance.slozka.rezim if instance.slozka_id else REZIM_MOJE
    return f'private/dokumentace/{rezim}/{instance.ulozene_jmeno}'


class DokumentSlozka(models.Model):
    nazev = models.CharField(max_length=200)
    parent = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='deti',
    )
    rezim = models.CharField(max_length=12, choices=REZIMY, db_index=True)
    vlastnik = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='dokument_slozky',
    )
    vytvoril = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='dokument_slozky_vytvoril',
    )
    vytvoreno = models.DateTimeField(auto_now_add=True)
    upraveno = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nazev']
        verbose_name = 'složka dokumentace'
        verbose_name_plural = 'složky dokumentace'

    def __str__(self):
        return self.nazev


class DokumentSoubor(models.Model):
    slozka = models.ForeignKey(
        DokumentSlozka,
        on_delete=models.CASCADE,
        related_name='soubory',
    )
    nazev = models.CharField(max_length=255)
    ulozene_jmeno = models.CharField(max_length=80, unique=True)
    soubor = models.FileField(upload_to=_upload_path)
    pripona = models.CharField(max_length=8)
    velikost = models.PositiveIntegerField()
    vlastnik = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='dokument_soubory',
    )
    vytvoreno = models.DateTimeField(auto_now_add=True)
    upraveno = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nazev']
        verbose_name = 'soubor dokumentace'
        verbose_name_plural = 'soubory dokumentace'

    def __str__(self):
        return self.nazev
