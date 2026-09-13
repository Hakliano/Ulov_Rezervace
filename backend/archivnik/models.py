from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from rezervace.models import Zamestnanec
from salons.models import Salon


class Stav(models.TextChoices):
    AKTIVNI = 'aktivni', 'Aktivní'
    ARCHIVOVANY = 'archivovany', 'Archivovaný'


class ReminderStav(models.TextChoices):
    AKTIVNI = 'aktivni', 'Aktivní'
    HOTOVO = 'hotovo', 'Hotovo'


class TagScope(models.TextChoices):
    ZAKAZNIK = 'zakaznik', 'Zákazník'
    OBJEKT = 'objekt', 'Objekt'
    OBE = 'obe', 'Zákazník i objekt'


class ArchivnikSession(models.Model):
    """Vlastní session Archivníku — nevytváří FLOW session."""

    zamestnanec = models.ForeignKey(
        Zamestnanec,
        related_name='archivnik_sessiony',
        on_delete=models.CASCADE,
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    vytvoreno = models.DateTimeField(auto_now_add=True)
    expirace = models.DateTimeField()

    class Meta:
        verbose_name = 'Archivník session'
        verbose_name_plural = 'Archivník sessiony'

    def je_platna(self):
        return self.zamestnanec.aktivni and timezone.now() < self.expirace


class ObjectType(models.Model):
    salon = models.ForeignKey(Salon, related_name='archivnik_object_types', on_delete=models.CASCADE)
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    nazev = models.CharField('název', max_length=80)
    poradi = models.PositiveSmallIntegerField(default=0)
    aktivni = models.BooleanField(default=True)
    vytvoreno = models.DateTimeField(auto_now_add=True)
    upraveno = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'typ objektu'
        verbose_name_plural = 'typy objektů'
        ordering = ['poradi', 'nazev']
        constraints = [
            models.UniqueConstraint(fields=['salon', 'nazev'], name='archivnik_objecttype_salon_nazev'),
        ]

    def __str__(self):
        return self.nazev


class Tag(models.Model):
    salon = models.ForeignKey(Salon, related_name='archivnik_tags', on_delete=models.CASCADE)
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    nazev = models.CharField('název', max_length=80)
    rozsah = models.CharField(max_length=16, choices=TagScope.choices, default=TagScope.OBE)
    vytvoreno = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'štítek'
        verbose_name_plural = 'štítky'
        ordering = ['nazev']
        constraints = [
            models.UniqueConstraint(fields=['salon', 'nazev'], name='archivnik_tag_salon_nazev'),
        ]

    def __str__(self):
        return self.nazev


class Customer(models.Model):
    salon = models.ForeignKey(Salon, related_name='archivnik_customers', on_delete=models.CASCADE)
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    jmeno = models.CharField('jméno', max_length=120, blank=True, default='')
    prijmeni = models.CharField('příjmení / název', max_length=160)
    telefon = models.CharField('telefon', max_length=40, blank=True, default='')
    email = models.EmailField('e-mail', blank=True, default='')
    adresa = models.CharField('adresa', max_length=300, blank=True, default='')
    poznamka = models.TextField('interní poznámka', blank=True, default='')
    stav = models.CharField(max_length=16, choices=Stav.choices, default=Stav.AKTIVNI, db_index=True)
    vytvoril = models.ForeignKey(
        Zamestnanec, related_name='archivnik_customers_vytvorene',
        on_delete=models.SET_NULL, null=True, blank=True,
    )
    zmenil = models.ForeignKey(
        Zamestnanec, related_name='archivnik_customers_zmenene',
        on_delete=models.SET_NULL, null=True, blank=True,
    )
    tagy = models.ManyToManyField(Tag, related_name='zakaznici', blank=True)
    vytvoreno = models.DateTimeField(auto_now_add=True)
    upraveno = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'zákazník'
        verbose_name_plural = 'zákazníci'
        ordering = ['prijmeni', 'jmeno']
        indexes = [
            models.Index(fields=['salon', 'prijmeni', 'jmeno']),
            models.Index(fields=['salon', 'telefon']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['salon', 'email'],
                condition=~models.Q(email=''),
                name='archivnik_customer_salon_email',
            ),
        ]

    def __str__(self):
        return self.display_name

    @property
    def display_name(self):
        parts = [self.jmeno.strip(), self.prijmeni.strip()]
        return ' '.join(p for p in parts if p) or f'Zákazník {self.uuid.hex[:8]}'


class Object(models.Model):
    salon = models.ForeignKey(Salon, related_name='archivnik_objects', on_delete=models.CASCADE)
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    zakaznik = models.ForeignKey(Customer, related_name='objekty', on_delete=models.CASCADE)
    typ = models.ForeignKey(
        ObjectType, related_name='objekty', on_delete=models.PROTECT,
    )
    nazev = models.CharField('název', max_length=160)
    popis = models.TextField('popis', blank=True, default='')
    stav = models.CharField(max_length=16, choices=Stav.choices, default=Stav.AKTIVNI, db_index=True)
    vytvoril = models.ForeignKey(
        Zamestnanec, related_name='archivnik_objects_vytvorene',
        on_delete=models.SET_NULL, null=True, blank=True,
    )
    zmenil = models.ForeignKey(
        Zamestnanec, related_name='archivnik_objects_zmenene',
        on_delete=models.SET_NULL, null=True, blank=True,
    )
    tagy = models.ManyToManyField(Tag, related_name='objekty', blank=True)
    vytvoreno = models.DateTimeField(auto_now_add=True)
    upraveno = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'objekt'
        verbose_name_plural = 'objekty'
        ordering = ['nazev']
        indexes = [
            models.Index(fields=['salon', 'nazev']),
        ]
        constraints = [
            models.UniqueConstraint(fields=['id', 'zakaznik'], name='archivnik_object_id_zakaznik'),
        ]

    def __str__(self):
        return self.nazev

    def clean(self):
        if self.zakaznik_id and self.zakaznik.salon_id != self.salon_id:
            raise ValidationError('Objekt musí patřit do stejné provozovny jako zákazník.')
        if self.typ_id and self.typ.salon_id != self.salon_id:
            raise ValidationError('Typ objektu patří jiné provozovně.')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class Entry(models.Model):
    """Zápis vždy patří zákazníkovi; objekt je volitelný kontext."""

    salon = models.ForeignKey(Salon, related_name='archivnik_entries', on_delete=models.CASCADE)
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    zakaznik = models.ForeignKey(Customer, related_name='zapisy', on_delete=models.CASCADE)
    objekt = models.ForeignKey(
        Object, related_name='zapisy', on_delete=models.CASCADE,
        null=True, blank=True,
    )
    nastalo = models.DateTimeField('datum a čas zápisu', default=timezone.now)
    typ_zapisu = models.CharField('typ zápisu', max_length=80, default='Poznámka')
    nadpis = models.CharField('nadpis', max_length=200, blank=True, default='')
    text = models.TextField('text')
    vytvoril = models.ForeignKey(
        Zamestnanec, related_name='archivnik_entries_vytvorene',
        on_delete=models.SET_NULL, null=True, blank=True,
    )
    zmenil = models.ForeignKey(
        Zamestnanec, related_name='archivnik_entries_zmenene',
        on_delete=models.SET_NULL, null=True, blank=True,
    )
    vytvoreno = models.DateTimeField(auto_now_add=True)
    upraveno = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'zápis'
        verbose_name_plural = 'zápisy'
        ordering = ['-nastalo', '-vytvoreno']
        indexes = [
            models.Index(fields=['salon', '-nastalo']),
            models.Index(fields=['zakaznik', '-nastalo']),
        ]

    def clean(self):
        if self.zakaznik_id and self.zakaznik.salon_id != self.salon_id:
            raise ValidationError('Zápis musí patřit do provozovny zákazníka.')
        if self.objekt_id:
            if self.objekt.zakaznik_id != self.zakaznik_id:
                raise ValidationError('Objekt zápisu musí patřit stejnému zákazníkovi.')
            if self.objekt.salon_id != self.salon_id:
                raise ValidationError('Objekt zápisu patří jiné provozovně.')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class Reminder(models.Model):
    salon = models.ForeignKey(Salon, related_name='archivnik_reminders', on_delete=models.CASCADE)
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    zakaznik = models.ForeignKey(Customer, related_name='pripominky', on_delete=models.CASCADE)
    objekt = models.ForeignKey(
        Object, related_name='pripominky', on_delete=models.CASCADE,
        null=True, blank=True,
    )
    termin = models.DateField('termín')
    text = models.CharField('text', max_length=300)
    prirazeny = models.ForeignKey(
        Zamestnanec, related_name='archivnik_pripominky',
        on_delete=models.SET_NULL, null=True, blank=True,
    )
    stav = models.CharField(max_length=16, choices=ReminderStav.choices, default=ReminderStav.AKTIVNI, db_index=True)
    vytvoril = models.ForeignKey(
        Zamestnanec, related_name='archivnik_reminders_vytvorene',
        on_delete=models.SET_NULL, null=True, blank=True,
    )
    vytvoreno = models.DateTimeField(auto_now_add=True)
    upraveno = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'připomínka'
        verbose_name_plural = 'připomínky'
        ordering = ['termin', 'id']

    def clean(self):
        if self.zakaznik_id and self.zakaznik.salon_id != self.salon_id:
            raise ValidationError('Připomínka musí patřit do provozovny zákazníka.')
        if self.objekt_id:
            if self.objekt.zakaznik_id != self.zakaznik_id:
                raise ValidationError('Objekt připomínky musí patřit stejnému zákazníkovi.')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
