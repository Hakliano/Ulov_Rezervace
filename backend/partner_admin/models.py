import uuid
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

from salons.models import Salon


variabilni_symbol_validator = RegexValidator(
    regex=r'^\d{1,10}$',
    message='Variabilní symbol musí obsahovat 1 až 10 číslic.',
)


class PartnerNastaveni(models.Model):
    STAV_ACTIVE = 'active'
    STAV_BLOCKED = 'blocked'
    STAVY = [
        (STAV_ACTIVE, 'ACTIVE'),
        (STAV_BLOCKED, 'BLOCKED'),
    ]

    PERIODA_MESIC = 'monthly'
    PERIODA_ROK = 'yearly'
    PERIODY = [
        (PERIODA_MESIC, 'Měsíčně'),
        (PERIODA_ROK, 'Ročně'),
    ]

    salon = models.OneToOneField(
        Salon,
        related_name='partner_nastaveni',
        on_delete=models.CASCADE,
    )
    domena = models.CharField('vlastní doména', max_length=253, blank=True)
    stav = models.CharField('stav služby', max_length=20, choices=STAVY, default=STAV_ACTIVE, db_index=True)
    tarif = models.CharField('tarif', max_length=100, blank=True)
    fakturacni_email = models.EmailField('fakturační e-mail', blank=True)
    variabilni_symbol = models.CharField(
        'variabilní symbol',
        max_length=10,
        unique=True,
        null=True,
        blank=True,
        validators=[variabilni_symbol_validator],
    )
    periodicita = models.CharField(
        'periodicita',
        max_length=20,
        choices=PERIODY,
        default=PERIODA_MESIC,
    )
    castka = models.DecimalField('částka', max_digits=10, decimal_places=2, default=Decimal('0.00'))
    dalsi_splatnost = models.DateField('další splatnost', null=True, blank=True, db_index=True)
    blokovan_od = models.DateTimeField('blokován od', null=True, blank=True)
    duvod_blokace = models.CharField('důvod blokace', max_length=300, blank=True)
    aktualizovano = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'nastavení partnera'
        verbose_name_plural = 'nastavení partnerů'
        ordering = ['salon__name']
        constraints = [
            models.UniqueConstraint(
                fields=['domena'],
                condition=~models.Q(domena=''),
                name='unique_nonempty_partner_domain',
            ),
        ]

    def __str__(self):
        return f'{self.salon.name} — {self.get_stav_display()}'

    def clean(self):
        super().clean()
        if self.variabilni_symbol == '':
            self.variabilni_symbol = None
        self.domena = self.domena.strip().lower().removeprefix('https://').removeprefix('http://').rstrip('/')
        if '/' in self.domena:
            raise ValidationError({'domena': 'Zadejte pouze doménu bez cesty.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        if self.stav == self.STAV_BLOCKED and not self.blokovan_od:
            self.blokovan_od = timezone.now()
        elif self.stav == self.STAV_ACTIVE:
            self.blokovan_od = None
            self.duvod_blokace = ''
        super().save(*args, **kwargs)

    @property
    def je_po_splatnosti(self):
        return bool(self.dalsi_splatnost and self.dalsi_splatnost < date.today())

    @property
    def dni_po_splatnosti(self):
        if not self.je_po_splatnosti:
            return 0
        return (date.today() - self.dalsi_splatnost).days

    @property
    def platebni_stav(self):
        if not self.dalsi_splatnost:
            return 'nenastaveno'
        if self.je_po_splatnosti:
            return 'po_splatnosti'
        return 'v_poradku'


class PlatbaPartnera(models.Model):
    salon = models.ForeignKey(Salon, related_name='partnerske_platby', on_delete=models.CASCADE)
    splatnost = models.DateField('původní splatnost')
    zaplaceno_dne = models.DateField('zaplaceno dne')
    ocekavana_castka = models.DecimalField(max_digits=10, decimal_places=2)
    prijata_castka = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    variabilni_symbol = models.CharField(max_length=10, blank=True)
    poznamka = models.CharField(max_length=300, blank=True)
    oznacil = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='oznacene_partnerske_platby',
    )
    vytvoreno = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'platba partnera'
        verbose_name_plural = 'platby partnerů'
        ordering = ['-splatnost', '-id']
        constraints = [
            models.UniqueConstraint(fields=['salon', 'splatnost'], name='unique_partner_payment_due_date'),
        ]

    def __str__(self):
        return f'{self.salon.name}: {self.splatnost:%d.%m.%Y}'


class UpozorneniPlatby(models.Model):
    salon = models.ForeignKey(Salon, related_name='upozorneni_plateb', on_delete=models.CASCADE)
    splatnost = models.DateField()
    prijemce = models.EmailField()
    predmet = models.CharField(max_length=200)
    text = models.TextField(blank=True)
    uspesne = models.BooleanField(default=False)
    chyba = models.CharField(max_length=500, blank=True)
    odeslal = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='odeslana_upozorneni_plateb',
    )
    odeslano = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'upozornění platby'
        verbose_name_plural = 'upozornění plateb'
        ordering = ['-odeslano']


class TechnickaChyba(models.Model):
    salon = models.ForeignKey(
        Salon,
        related_name='technicke_chyby',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    request_id = models.UUIDField(default=uuid.uuid4, editable=False, db_index=True)
    cas = models.DateTimeField(auto_now_add=True, db_index=True)
    metoda = models.CharField(max_length=10, blank=True)
    cesta = models.CharField(max_length=500)
    typ_chyby = models.CharField(max_length=200)
    detail = models.CharField(max_length=500, blank=True)
    vyreseno = models.BooleanField(default=False, db_index=True)

    class Meta:
        verbose_name = 'technická chyba'
        verbose_name_plural = 'technické chyby'
        ordering = ['-cas']

    def __str__(self):
        return f'{self.cas:%d.%m.%Y %H:%M} — {self.typ_chyby}'
