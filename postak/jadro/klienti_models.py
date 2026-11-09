from django.conf import settings
from django.db import models


class KlientSektor(models.Model):
    remote_id = models.PositiveIntegerField(unique=True)
    nazev = models.CharField(max_length=80)
    razeni = models.PositiveSmallIntegerField(default=100)

    class Meta:
        ordering = ['razeni', 'nazev']

    def __str__(self):
        return self.nazev


class KlientModernik(models.Model):
    remote_id = models.PositiveIntegerField(unique=True, db_index=True)
    jmeno = models.CharField(max_length=200, db_index=True)
    email = models.EmailField(db_index=True)
    telefon = models.CharField(max_length=200, blank=True, default='')
    web = models.CharField(max_length=400, blank=True, default='')
    adresa = models.TextField(blank=True, default='')
    ico = models.CharField(max_length=20, blank=True, default='')
    poznamka = models.TextField(blank=True, default='')
    stav = models.CharField(max_length=32, db_index=True)
    stav_label = models.CharField(max_length=80, blank=True, default='')
    sektor_remote_id = models.PositiveIntegerField(null=True, blank=True)
    sektor_nazev = models.CharField(max_length=80, blank=True, default='')
    remote_upraveno = models.DateTimeField()
    cached = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-remote_upraveno']
        verbose_name = 'klient Moderník (cache)'
        verbose_name_plural = 'klienti Moderník (cache)'


class KlientHya(models.Model):
    remote_id = models.PositiveIntegerField(unique=True, db_index=True)
    jmeno = models.CharField(max_length=200, db_index=True)
    kontakt_jmeno = models.CharField(max_length=200, blank=True, default='')
    email = models.EmailField(max_length=254, blank=True, default='', db_index=True)
    telefon = models.CharField(max_length=200, blank=True, default='')
    web = models.CharField(max_length=400, blank=True, default='')
    lokalita = models.CharField(max_length=200, blank=True, default='')
    zdroj = models.CharField(max_length=120, blank=True, default='')
    ma_web = models.CharField(max_length=12, blank=True, default='')  # yes|no|unknown
    ma_rezervace = models.CharField(max_length=12, blank=True, default='')
    poznamka = models.TextField(blank=True, default='')
    stav = models.CharField(max_length=32, db_index=True)
    stav_label = models.CharField(max_length=80, blank=True, default='')
    remote_upraveno = models.DateTimeField()
    cached = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-remote_upraveno']
        verbose_name = 'klient HereYouAre (cache)'
        verbose_name_plural = 'klienti HereYouAre (cache)'


class KlientSyncMeta(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, editable=False)
    posledni_delta = models.DateTimeField(null=True, blank=True)
    posledni_nocni = models.DateTimeField(null=True, blank=True)
    posledni_chyba = models.CharField(max_length=300, blank=True, default='')


class KlientStavHistorie(models.Model):
    klient = models.ForeignKey(KlientModernik, on_delete=models.CASCADE, related_name='stav_historie')
    stav = models.CharField(max_length=32)
    stav_pred = models.CharField(max_length=32, blank=True, default='')
    stav_label = models.CharField(max_length=80, blank=True, default='')
    kdo = models.CharField(max_length=120, blank=True, default='')
    kdy = models.DateTimeField()

    class Meta:
        ordering = ['-kdy']
