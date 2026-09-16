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


class Obor(models.Model):
    """Tenant-specific složka konfigurace. Není evidenční entita kartotéky."""

    salon = models.ForeignKey(Salon, related_name='archivnik_obory', on_delete=models.CASCADE)
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    nazev = models.CharField('název', max_length=80)
    poradi = models.PositiveSmallIntegerField(default=0)
    zdroj_preset = models.CharField(
        max_length=32, blank=True, default='',
        help_text='Kód presetu v okamžiku kopie. Nikdy se z katalogu znovu nesynchronizuje.',
    )
    objekt_jednotne = models.CharField('jednotné číslo objektu', max_length=40, default='Objekt')
    objekt_mnozne = models.CharField('množné číslo objektu', max_length=40, default='Objekty')
    aktualni = models.BooleanField(default=False)
    vytvoreno = models.DateTimeField(auto_now_add=True)
    upraveno = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'obor'
        verbose_name_plural = 'obory'
        ordering = ['poradi', 'nazev']
        constraints = [
            models.UniqueConstraint(fields=['salon', 'nazev'], name='archivnik_obor_salon_nazev'),
            models.UniqueConstraint(
                fields=['salon', 'zdroj_preset'],
                condition=~models.Q(zdroj_preset=''),
                name='archivnik_obor_salon_preset',
            ),
            models.UniqueConstraint(
                fields=['salon'],
                condition=models.Q(aktualni=True),
                name='archivnik_obor_salon_jeden_aktualni',
            ),
        ]

    def __str__(self):
        return self.nazev

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class ObjectType(models.Model):
    salon = models.ForeignKey(Salon, related_name='archivnik_object_types', on_delete=models.CASCADE)
    obor = models.ForeignKey(
        Obor, related_name='typy', on_delete=models.SET_NULL,
        null=True, blank=True,
    )
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    nazev = models.CharField('název', max_length=80)
    poradi = models.PositiveSmallIntegerField(default=0)
    aktivni = models.BooleanField(default=True)
    vyzaduje_nazev = models.BooleanField('vyžaduje název objektu', default=True)
    zdroj_preset = models.CharField(max_length=32, blank=True, default='')
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

    def clean(self):
        if self.obor_id and self.obor.salon_id != self.salon_id:
            raise ValidationError('Obor musí patřit stejné provozovně.')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


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
    nazev = models.CharField('název', max_length=160, blank=True, default='')
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
    cover = models.ForeignKey(
        'Asset',
        related_name='+',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='hlavní fotografie',
    )
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

    @property
    def display_name(self):
        n = (self.nazev or '').strip()
        if n:
            return n
        if self.typ_id:
            return self.typ.nazev
        return 'Bez názvu'

    def __str__(self):
        return self.display_name

    def clean(self):
        if self.typ_id and self.typ.vyzaduje_nazev and not (self.nazev or '').strip():
            raise ValidationError({'nazev': 'Tento typ objektu vyžaduje název.'})
        if self.zakaznik_id and self.zakaznik.salon_id != self.salon_id:
            raise ValidationError('Objekt musí patřit do stejné provozovny jako zákazník.')
        if self.typ_id and self.typ.salon_id != self.salon_id:
            raise ValidationError('Typ objektu patří jiné provozovně.')
        if self.typ_id and self.typ.obor_id and self.typ.obor.salon_id != self.salon_id:
            raise ValidationError('Obor typu objektu patří jiné provozovně.')
        if self.cover_id:
            if self.cover.salon_id != self.salon_id:
                raise ValidationError('Hlavní fotografie patří jiné provozovně.')
            if self.cover.objekt_id != self.pk:
                raise ValidationError('Hlavní fotografie musí patřit tomuto objektu.')
            if self.cover.druh != 'fotografie':
                raise ValidationError('Hlavní fotografie musí být fotografie.')

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


class FieldKind(models.TextChoices):
    TEXT = 'text', 'Text'
    DLOUHY_TEXT = 'dlouhy_text', 'Dlouhý text'
    CISLO = 'cislo', 'Číslo'
    DATUM = 'datum', 'Datum'
    ANO_NE = 'ano_ne', 'Ano / ne'
    VYBER = 'vyber', 'Výběr'


class CustomFieldDef(models.Model):
    """Definice vlastního pole visí na typu objektu, ne na segmentu trhu."""

    salon = models.ForeignKey(Salon, related_name='archivnik_field_defs', on_delete=models.CASCADE)
    typ = models.ForeignKey(ObjectType, related_name='pole', on_delete=models.CASCADE)
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    nazev = models.CharField('název', max_length=80)
    druh = models.CharField(max_length=16, choices=FieldKind.choices, default=FieldKind.TEXT)
    volby = models.JSONField('možnosti výběru', default=list, blank=True)
    poradi = models.PositiveSmallIntegerField(default=0)
    aktivni = models.BooleanField(default=True)
    zdroj_preset = models.CharField(max_length=32, blank=True, default='')
    vytvoreno = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'vlastní pole'
        verbose_name_plural = 'vlastní pole'
        ordering = ['poradi', 'id']
        constraints = [
            models.UniqueConstraint(fields=['typ', 'nazev'], name='archivnik_fielddef_typ_nazev'),
        ]

    def __str__(self):
        return self.nazev

    def clean(self):
        if self.typ_id and self.typ.salon_id != self.salon_id:
            raise ValidationError('Definice pole musí patřit stejné provozovně jako typ objektu.')
        if not isinstance(self.volby, list):
            raise ValidationError('Možnosti výběru musí být seznam.')
        self.volby = [str(v).strip() for v in self.volby if str(v).strip()]
        if self.druh == FieldKind.VYBER and len(self.volby) < 2:
            raise ValidationError('Výběr potřebuje alespoň dvě možnosti.')
        if self.druh != FieldKind.VYBER:
            self.volby = []

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class CustomFieldValue(models.Model):
    objekt = models.ForeignKey(Object, related_name='hodnoty_poli', on_delete=models.CASCADE)
    pole = models.ForeignKey(CustomFieldDef, related_name='hodnoty', on_delete=models.CASCADE)
    hodnota = models.TextField(blank=True, default='')

    class Meta:
        verbose_name = 'hodnota vlastního pole'
        verbose_name_plural = 'hodnoty vlastních polí'
        constraints = [
            models.UniqueConstraint(fields=['objekt', 'pole'], name='archivnik_fieldvalue_objekt_pole'),
        ]

    def clean(self):
        if self.pole_id and self.objekt_id:
            if self.pole.typ_id != self.objekt.typ_id:
                raise ValidationError('Pole nepatří k typu tohoto objektu.')
            if self.pole.salon_id != self.objekt.salon_id:
                raise ValidationError('Pole patří jiné provozovně.')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class AssetKind(models.TextChoices):
    FOTOGRAFIE = 'fotografie', 'Fotografie'
    DOKUMENT = 'dokument', 'Dokument'


class Asset(models.Model):
    """Jeden soubor na Bunny. Zákazník povinný, objekt i zápis volitelné."""

    salon = models.ForeignKey(Salon, related_name='archivnik_assets', on_delete=models.CASCADE)
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    zakaznik = models.ForeignKey(Customer, related_name='soubory', on_delete=models.CASCADE)
    objekt = models.ForeignKey(
        Object, related_name='soubory', on_delete=models.CASCADE,
        null=True, blank=True,
    )
    zapis = models.ForeignKey(
        Entry, related_name='prilohy', on_delete=models.SET_NULL,
        null=True, blank=True,
    )
    druh = models.CharField(max_length=16, choices=AssetKind.choices, default=AssetKind.DOKUMENT)
    nazev = models.CharField('název', max_length=200)
    content_type = models.CharField(max_length=80)
    velikost = models.PositiveIntegerField(default=0)
    storage_key = models.CharField(max_length=400)
    vytvoril = models.ForeignKey(
        Zamestnanec, related_name='archivnik_assets_vytvorene',
        on_delete=models.SET_NULL, null=True, blank=True,
    )
    vytvoreno = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'soubor'
        verbose_name_plural = 'soubory'
        ordering = ['-vytvoreno']
        indexes = [
            models.Index(fields=['salon', 'zakaznik']),
            models.Index(fields=['objekt', 'druh']),
        ]

    def __str__(self):
        return self.nazev

    def clean(self):
        if self.zakaznik_id and self.zakaznik.salon_id != self.salon_id:
            raise ValidationError('Soubor musí patřit do provozovny zákazníka.')
        if self.objekt_id:
            if self.objekt.zakaznik_id != self.zakaznik_id:
                raise ValidationError('Objekt souboru musí patřit stejnému zákazníkovi.')
            if self.objekt.salon_id != self.salon_id:
                raise ValidationError('Objekt souboru patří jiné provozovně.')
        if self.zapis_id:
            if self.zapis.zakaznik_id != self.zakaznik_id:
                raise ValidationError('Zápis souboru musí patřit stejnému zákazníkovi.')
            if self.objekt_id and self.zapis.objekt_id and self.zapis.objekt_id != self.objekt_id:
                raise ValidationError('Příloha zápisu musí zůstat u stejného objektu.')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
