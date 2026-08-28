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


def vychozi_variabilni_symbol(salon_id):
    """80 a hned ID partnera, např. salon 19 → 8019."""
    if not salon_id:
        return ''
    vs = f'80{salon_id}'
    return vs if len(vs) <= 10 else ''


class KeyAccountManager(models.Model):
    jmeno = models.CharField('jméno', max_length=120, unique=True)
    email = models.EmailField('e-mail', blank=True)
    telefon = models.CharField('telefon', max_length=50, blank=True)
    cislo_uctu = models.CharField('číslo účtu', max_length=34, blank=True)
    aktivni = models.BooleanField('aktivní', default=True)
    razeni = models.PositiveSmallIntegerField('pořadí', default=0)

    class Meta:
        verbose_name = 'KAM'
        verbose_name_plural = 'KAM'
        ordering = ['razeni', 'jmeno']

    def __str__(self):
        return self.jmeno


class UlovCisloUctu(models.Model):
    cislo = models.CharField('číslo účtu', max_length=34, unique=True)
    popisek = models.CharField('kam / poznámka', max_length=80, blank=True)
    primarni = models.BooleanField('primární (QR)', default=False)
    aktivni = models.BooleanField('aktivní', default=True)
    razeni = models.PositiveSmallIntegerField('pořadí', default=0)

    class Meta:
        verbose_name = 'číslo účtu ULOV'
        verbose_name_plural = 'čísla účtů ULOV'
        ordering = ['-primarni', 'razeni', 'id']

    def __str__(self):
        return self.cislo

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.primarni and self.pk:
            UlovCisloUctu.objects.exclude(pk=self.pk).update(primarni=False)


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
    ulov_cislo_uctu = models.CharField(
        'účet ULOV (pro QR / převod)',
        max_length=34,
        blank=True,
        help_text='Číslo účtu ULOV ve formátu číslo/kód banky nebo IBAN. Není to účet personálu.',
    )
    blokovan_od = models.DateTimeField('blokován od', null=True, blank=True)
    duvod_blokace = models.CharField('důvod blokace', max_length=300, blank=True)
    povolit_technicke_nastaveni = models.BooleanField(
        'povolit Technické nastavení ve FLOW',
        default=False,
        help_text=(
            'Když je zapnuto, majitel ve FLOW Správě vidí zónu Technické nastavení '
            '(rezervační pravidla, e-mailové šablony, audit log).'
        ),
    )
    tenant_uuid = models.UUIDField(
        'veřejné ID tenanta',
        default=uuid.uuid4,
        unique=True,
        editable=False,
        help_text='Stabilní identita salonu vůči Materiálníku a dalším modulům. Není to interní salon.id.',
    )
    kam = models.ForeignKey(
        'KeyAccountManager',
        verbose_name='KAM',
        related_name='partneri',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    prvni_platba = models.DecimalField(
        'první platba',
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Instalační balíček nebo první tarif. V tom měsíci se už nenačítá další 499/598.',
    )
    kam_provize = models.DecimalField(
        'provize KAM',
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Kolik dostane KAM po zaplacení první platby. 0 = nepočítat.',
    )
    kam_procento = models.DecimalField(
        'provize KAM z dalších plateb (%)',
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text='Volitelné. Z přijatých plateb po první platbě.',
    )
    ico = models.CharField('IČO odběratele', max_length=12, blank=True)
    je_testovaci = models.BooleanField(
        'testovací partner',
        default=False,
        db_index=True,
        help_text='Jen interní dema. Noví zákazníci sem nepatří. Viditelné v Testovacích přístupech.',
    )
    zalozeno = models.DateTimeField('založeno', default=timezone.now, db_index=True, editable=False)
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


class PartnerTarif(models.Model):
    """Katalog tarifů pro partner-admin. U partnera se uloží název + (případně upravená) cena."""

    nazev = models.CharField('název', max_length=100, unique=True)
    castka = models.DecimalField('výchozí cena', max_digits=10, decimal_places=2, default=Decimal('0.00'))
    razeni = models.PositiveSmallIntegerField('pořadí', default=0)
    aktivni = models.BooleanField('aktivní', default=True)

    class Meta:
        verbose_name = 'tarif'
        verbose_name_plural = 'tarify'
        ordering = ['razeni', 'id']

    def __str__(self):
        return self.nazev


class PlatbaPartnera(models.Model):
    salon = models.ForeignKey(Salon, related_name='partnerske_platby', on_delete=models.CASCADE)
    splatnost = models.DateField('původní splatnost')
    zaplaceno_dne = models.DateField('zaplaceno dne')
    ocekavana_castka = models.DecimalField(max_digits=10, decimal_places=2)
    prijata_castka = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    variabilni_symbol = models.CharField(max_length=10, blank=True)
    poznamka = models.CharField(max_length=300, blank=True)
    faktura_pdf = models.FileField(
        'faktura PDF',
        upload_to='partner_faktury/%Y/%m/',
        blank=True,
        null=True,
    )
    cislo_faktury = models.CharField('číslo faktury', max_length=30, blank=True)
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


class KamProvize(models.Model):
    TYP_PRVNI = 'prvni'
    TYP_PROCENTO = 'procento'
    TYPY = [
        (TYP_PRVNI, 'První platba'),
        (TYP_PROCENTO, 'Procento z přijatého'),
    ]
    STAV_K_VYPLATE = 'k_vyplate'
    STAV_VYPLACENO = 'vyplaceno'
    STAVY = [
        (STAV_K_VYPLATE, 'K výplatě'),
        (STAV_VYPLACENO, 'Vyplaceno'),
    ]

    kam = models.ForeignKey(
        KeyAccountManager,
        related_name='provize',
        on_delete=models.CASCADE,
    )
    salon = models.ForeignKey(Salon, related_name='kam_provize', on_delete=models.CASCADE)
    platba = models.OneToOneField(
        PlatbaPartnera,
        related_name='kam_provize',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    typ = models.CharField(max_length=20, choices=TYPY, default=TYP_PRVNI)
    obdobi = models.DateField('období (1. den měsíce)', db_index=True)
    castka = models.DecimalField(max_digits=10, decimal_places=2)
    prvni_platba = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    stav = models.CharField(max_length=20, choices=STAVY, default=STAV_K_VYPLATE, db_index=True)
    uvolneno_dne = models.DateField()
    vyplaceno_dne = models.DateField(null=True, blank=True)
    poznamka = models.CharField(max_length=300, blank=True)

    class Meta:
        verbose_name = 'provize KAM'
        verbose_name_plural = 'provize KAM'
        ordering = ['-obdobi', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['kam', 'salon', 'typ', 'obdobi'],
                name='unique_kam_provize_obdobi',
            ),
        ]

    def __str__(self):
        return f'{self.kam}: {self.castka} ({self.obdobi:%m/%Y})'


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
    query = models.CharField('query bez tajemství', max_length=400, blank=True)
    status_kod = models.PositiveSmallIntegerField('HTTP stav', null=True, blank=True)
    typ_chyby = models.CharField(max_length=200)
    detail = models.TextField(blank=True)
    stopa = models.TextField('traceback', blank=True)
    vyreseno = models.BooleanField(default=False, db_index=True)

    class Meta:
        verbose_name = 'technická chyba'
        verbose_name_plural = 'technické chyby'
        ordering = ['-cas']

    def __str__(self):
        return f'{self.cas:%d.%m.%Y %H:%M} — {self.typ_chyby}'


MODUL_MATERIALNIK = 'materialnik'


class ModulKatalog(models.Model):
    kod = models.SlugField('kód', max_length=40, unique=True)
    nazev = models.CharField('název', max_length=80)
    popis = models.CharField('popis', max_length=300, blank=True)
    razeni = models.PositiveSmallIntegerField('pořadí', default=0)

    class Meta:
        verbose_name = 'modul v katalogu'
        verbose_name_plural = 'katalog modulů'
        ordering = ['razeni', 'kod']

    def __str__(self):
        return self.nazev


class PartnerModul(models.Model):
    STAV_PENDING = 'pending'
    STAV_ACTIVE = 'active'
    STAV_INACTIVE = 'inactive'
    STAV_ERROR = 'error'
    STAVY = [
        (STAV_PENDING, 'Zapíná se'),
        (STAV_ACTIVE, 'Aktivní'),
        (STAV_INACTIVE, 'Vypnuto'),
        (STAV_ERROR, 'Chyba'),
    ]

    salon = models.ForeignKey(Salon, related_name='moduly', on_delete=models.CASCADE)
    modul = models.ForeignKey(ModulKatalog, related_name='partneri', on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=STAVY, default=STAV_INACTIVE, db_index=True)
    hmac_key = models.CharField(max_length=128, blank=True)
    provisioning_error = models.TextField('chyba provisioningu', blank=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)
    aktualizovano = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'modul partnera'
        verbose_name_plural = 'moduly partnerů'
        unique_together = [('salon', 'modul')]

    def __str__(self):
        return f'{self.salon_id}:{self.modul.kod}={self.status}'

    @property
    def je_aktivni(self):
        return self.status == self.STAV_ACTIVE


class IntegrationOutbox(models.Model):
    STAV_PENDING = 'pending'
    STAV_SENT = 'sent'
    STAV_FAILED = 'failed'
    STAV_SKIPPED = 'skipped'
    STAVY = [
        (STAV_PENDING, 'Čeká'),
        (STAV_SENT, 'Odesláno'),
        (STAV_FAILED, 'Chyba'),
        (STAV_SKIPPED, 'Přeskočeno'),
    ]

    salon = models.ForeignKey(Salon, related_name='integration_outbox', on_delete=models.CASCADE)
    event_id = models.CharField(max_length=64, unique=True)
    event_type = models.CharField(max_length=80)
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=20, choices=STAVY, default=STAV_PENDING, db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    last_error = models.CharField(max_length=400, blank=True)
    next_attempt_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'integration outbox'
        verbose_name_plural = 'integration outbox'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['status', 'next_attempt_at']),
        ]

    def __str__(self):
        return f'{self.event_type}:{self.event_id[:12]}'


class HromadnyEmail(models.Model):
    OKRUH_VSICHNI = 'vsichni'
    OKRUH_PO_SPLATNOSTI = 'po_splatnosti'
    OKRUH_ACTIVE = 'active'
    OKRUH_TARIF = 'tarif'
    OKRUHY = [
        (OKRUH_VSICHNI, 'Všichni partneři s e-mailem'),
        (OKRUH_PO_SPLATNOSTI, 'Jen po splatnosti'),
        (OKRUH_ACTIVE, 'Jen ACTIVE'),
        (OKRUH_TARIF, 'Podle tarifu'),
    ]

    predmet = models.CharField(max_length=200)
    text = models.TextField()
    okruh = models.CharField(max_length=20, choices=OKRUHY, default=OKRUH_VSICHNI)
    tarif = models.CharField(max_length=100, blank=True)
    odeslano_pocet = models.PositiveIntegerField(default=0)
    preskoceno_pocet = models.PositiveIntegerField(default=0)
    chyba_pocet = models.PositiveIntegerField(default=0)
    odeslal = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='hromadne_emaily',
    )
    vytvoreno = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'hromadný e-mail'
        verbose_name_plural = 'hromadné e-maily'
        ordering = ['-vytvoreno']

    def __str__(self):
        return f'{self.predmet} ({self.odeslano_pocet})'


class ExtraFaktura(models.Model):
    """Jednorázová faktura partnerovi (vizitky, NFC…). Nemění splatnost tarifu."""

    STAV_UHRAZENO = 'uhrazeno'
    STAV_K_UHRADE = 'k_uhrade'
    STAVY = [
        (STAV_UHRAZENO, 'Uhrazeno'),
        (STAV_K_UHRADE, 'K úhradě'),
    ]

    salon = models.ForeignKey(Salon, related_name='extra_faktury', on_delete=models.CASCADE)
    cislo_faktury = models.CharField('číslo faktury', max_length=30, unique=True)
    variabilni_symbol = models.CharField('variabilní symbol', max_length=10, blank=True)
    popis = models.CharField('položka', max_length=200)
    castka = models.DecimalField(max_digits=10, decimal_places=2)
    stav = models.CharField(max_length=20, choices=STAVY, default=STAV_K_UHRADE, db_index=True)
    datum_vystaveni = models.DateField(db_index=True)
    datum_splatnosti = models.DateField(null=True, blank=True)
    datum_uhrady = models.DateField(null=True, blank=True)
    faktura_pdf = models.FileField(
        'faktura PDF',
        upload_to='partner_faktury/%Y/%m/',
        blank=True,
        null=True,
    )
    poznamka = models.CharField(max_length=300, blank=True)
    odeslana_emailem = models.BooleanField(default=False)
    vytvoril = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='extra_faktury',
    )
    vytvoreno = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'jednorázová faktura'
        verbose_name_plural = 'jednorázové faktury'
        ordering = ['-datum_vystaveni', '-id']

    def __str__(self):
        return f'{self.cislo_faktury} · {self.salon.name}'

    @property
    def je_k_uhrade(self):
        return self.stav == self.STAV_K_UHRADE


class Vydaj(models.Model):
    datum = models.DateField(db_index=True)
    castka = models.DecimalField(max_digits=10, decimal_places=2)
    ucet = models.ForeignKey(
        UlovCisloUctu,
        related_name='vydaje',
        on_delete=models.PROTECT,
    )
    salon = models.ForeignKey(
        Salon,
        related_name='vydaje',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text='Prázdné = generic výdaj, ne k partnerovi.',
    )
    poznamka = models.CharField(max_length=300)
    vytvoril = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='vydaje',
    )
    vytvoreno = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'výdaj'
        verbose_name_plural = 'výdaje'
        ordering = ['-datum', '-id']

    def __str__(self):
        return f'{self.datum:%d.%m.%Y} · {self.castka} Kč'


class VydajSablona(models.Model):
    nazev = models.CharField('název', max_length=80, unique=True)
    castka = models.DecimalField(max_digits=10, decimal_places=2)
    ucet = models.ForeignKey(
        UlovCisloUctu,
        related_name='vydaj_sablony',
        on_delete=models.PROTECT,
    )
    salon = models.ForeignKey(
        Salon,
        related_name='vydaj_sablony',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    poznamka = models.CharField(max_length=300, blank=True)
    vytvoreno = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'šablona výdaje'
        verbose_name_plural = 'šablony výdajů'
        ordering = ['nazev']

    def __str__(self):
        return self.nazev
