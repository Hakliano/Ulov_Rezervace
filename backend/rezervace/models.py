import uuid

from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.utils import timezone

from salons.models import CenikPolozka, OteviraciDoba, Salon


INTERVAL_CHOICES = [(5, '5 minut'), (10, '10 minut'), (15, '15 minut'), (30, '30 minut')]

STAV_REZERVACE = [
    ('ceka', 'Čeká na potvrzení'),
    ('potvrzeno', 'Potvrzeno'),
    ('zakaznik_storno', 'Zákazník zrušil'),
    ('salon_storno', 'Salon zrušil'),
    ('dokonceno', 'Dokončeno'),
    ('no_show', 'Zákazník se nedostavil'),
]

TYP_VYTVORENI = [
    ('online', 'Online'),
    ('telefon', 'Telefonicky'),
    ('osobne', 'Osobně'),
    ('zamestnanec', 'Zaměstnancem'),
]

TYP_ABSENCE = [
    ('volno', 'Volno'),
    ('dovolena', 'Dovolená'),
    ('nemoc', 'Nemoc'),
]

DENY = OteviraciDoba.DENY


class RezervacniNastaveni(models.Model):
    salon = models.OneToOneField(
        Salon, related_name='rezervacni_nastaveni', on_delete=models.CASCADE,
    )
    interval_minut = models.PositiveIntegerField('interval rezervací', choices=INTERVAL_CHOICES, default=15)
    min_predstih_hodin = models.PositiveIntegerField('min. předstih (h)', default=2)
    max_predstih_mesicu = models.PositiveIntegerField('max. předstih (měsíce)', default=3)
    notifikace = models.JSONField(
        'e-mailové notifikace',
        default=list,
        blank=True,
        help_text='Až 3 notifikace: offset +24 / -2, předmět, text, aktivní.',
    )
    storno_do_hodin = models.PositiveIntegerField('storno do (h)', null=True, blank=True)
    platba_qr_text = models.TextField('QR / platební instrukce', blank=True)
    auto_potvrzeni = models.BooleanField(
        'automatické potvrzení (personál)',
        default=False,
        help_text='Rezervace zadané zaměstnancem. Online rezervace vždy vyžadují potvrzení e-mailem.',
    )
    email_odesilatel = models.EmailField(
        'e-mail odesílatele', blank=True,
        help_text='Prázdné = použije se e-mail salonu z webu.',
    )
    email_jmeno_odesilatele = models.CharField(
        'jméno odesílatele', max_length=100, blank=True,
        help_text='Zobrazí se v poli Od: (např. Salon Elegance).',
    )
    smtp_host = models.CharField('SMTP server', max_length=200, blank=True, default='smtp.forpsi.com')
    smtp_port = models.PositiveIntegerField('SMTP port', default=465)
    smtp_use_ssl = models.BooleanField('SMTP SSL', default=True)
    smtp_user = models.EmailField('SMTP přihlášení', blank=True)
    smtp_password = models.CharField('SMTP heslo', max_length=200, blank=True)
    web_rezervace_url = models.URLField(
        'URL stránky rezervací',
        blank=True,
        help_text='Odkazy v e-mailech. Např. https://vase-domena.cz/rezervace.html',
    )
    recenze_url = models.URLField(
        'URL recenze',
        blank=True,
        default='',
        help_text='Odkaz na recenze (Google, Facebook…). Použijte v e-mailu jako {{ recenze_url }}.',
    )
    potvrzeni_platnost_hodin = models.PositiveIntegerField(
        'platnost odkazu na potvrzení (h)',
        default=24,
        help_text='Po vypršení se nepotvrzená online rezervace automaticky zruší.',
    )
    gdpr_zasady_verze = models.CharField(
        'verze Zásad ochrany osobních údajů',
        max_length=20,
        default='1.0',
        help_text='Aktuální verze zobrazená zákazníkům (např. 1.0, 1.2).',
    )

    class Meta:
        verbose_name = 'nastavení rezervací'
        verbose_name_plural = 'nastavení rezervací'

    def __str__(self):
        return f'Nastavení – {self.salon.name}'

    def save(self, *args, **kwargs):
        from rezervace.notifikace_defaults import normalizuj_notifikace
        self.notifikace = normalizuj_notifikace(self.notifikace)
        super().save(*args, **kwargs)


class StatniSvatky(models.Model):
    datum = models.DateField('datum', unique=True)
    nazev = models.CharField('název', max_length=100)

    class Meta:
        verbose_name = 'státní svátek'
        verbose_name_plural = 'státní svátky'
        ordering = ['datum']

    def __str__(self):
        return f'{self.datum} – {self.nazev}'


class SalonVyjimka(models.Model):
    salon = models.ForeignKey(Salon, related_name='vyjimky', on_delete=models.CASCADE)
    datum_od = models.DateField('od')
    datum_do = models.DateField('do')
    duvod = models.CharField('důvod', max_length=200, blank=True)

    class Meta:
        verbose_name = 'mimořádné uzavření'
        verbose_name_plural = 'mimořádná uzavření'
        ordering = ['datum_od']

    def __str__(self):
        return f'{self.salon.name}: {self.datum_od}–{self.datum_do}'


class Zamestnanec(models.Model):
    ROLE_MAJITEL = 'majitel'
    ROLE_ZAMESTNANEC = 'zamestnanec'
    ROLE_CHOICES = [
        (ROLE_MAJITEL, 'Majitel / majitelka'),
        (ROLE_ZAMESTNANEC, 'Zaměstnanec'),
    ]

    salon = models.ForeignKey(Salon, related_name='zamestnanci', on_delete=models.CASCADE)
    jmeno = models.CharField('jméno', max_length=100)
    specializace = models.CharField('specializace', max_length=200, blank=True)
    popis = models.TextField('popis na webu', blank=True)
    fotka = models.URLField('fotka', blank=True)
    zobrazit_na_webu = models.BooleanField('zobrazit na webu', default=True)
    aktivni = models.BooleanField('aktivní', default=True)
    poradi = models.PositiveIntegerField('pořadí', default=0)
    cislo_uctu = models.CharField('číslo účtu', max_length=34, blank=True)
    prihlasovaci_jmeno = models.CharField('přihlašovací jméno', max_length=50, blank=True)
    password_hash = models.CharField('heslo (hash)', max_length=128, blank=True)
    role = models.CharField('role', max_length=20, choices=ROLE_CHOICES, default=ROLE_ZAMESTNANEC)

    class Meta:
        verbose_name = 'zaměstnanec'
        verbose_name_plural = 'zaměstnanci'
        ordering = ['poradi', 'id']
        unique_together = ['salon', 'prihlasovaci_jmeno']

    def __str__(self):
        return self.jmeno

    @property
    def ma_prihlaseni(self):
        return bool(self.prihlasovaci_jmeno and self.password_hash)

    def set_password(self, raw_password):
        self.password_hash = make_password(raw_password)

    def check_password(self, raw_password):
        if not self.password_hash:
            return False
        return check_password(raw_password, self.password_hash)


class ZamestnanecSession(models.Model):
    zamestnanec = models.ForeignKey(Zamestnanec, related_name='sessiony', on_delete=models.CASCADE)
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    vytvoreno = models.DateTimeField(auto_now_add=True)
    expirace = models.DateTimeField()

    class Meta:
        verbose_name = 'session zaměstnance'
        verbose_name_plural = 'sessiony zaměstnanců'

    def je_platna(self):
        return timezone.now() < self.expirace


class ZamestnanecRozvrh(models.Model):
    zamestnanec = models.ForeignKey(Zamestnanec, related_name='rozvrh', on_delete=models.CASCADE)
    den = models.IntegerField('den', choices=DENY)
    od = models.TimeField('od', null=True, blank=True)
    do = models.TimeField('do', null=True, blank=True)
    volno = models.BooleanField('volno', default=False)

    class Meta:
        verbose_name = 'rozvrh zaměstnance'
        verbose_name_plural = 'rozvrhy zaměstnanců'
        unique_together = ['zamestnanec', 'den']
        ordering = ['den']

    def __str__(self):
        if self.volno:
            return f'{self.zamestnanec.jmeno} – {self.get_den_display()} volno'
        return f'{self.zamestnanec.jmeno} – {self.get_den_display()} {self.od}–{self.do}'


class ZamestnanecAbsence(models.Model):
    zamestnanec = models.ForeignKey(Zamestnanec, related_name='absence', on_delete=models.CASCADE)
    datum_od = models.DateField('od')
    datum_do = models.DateField('do')
    typ = models.CharField('typ', max_length=20, choices=TYP_ABSENCE, default='dovolena')
    poznamka = models.CharField('poznámka', max_length=200, blank=True)

    class Meta:
        verbose_name = 'absence zaměstnance'
        verbose_name_plural = 'absence zaměstnanců'
        ordering = ['datum_od']

    def __str__(self):
        return f'{self.zamestnanec.jmeno}: {self.datum_od}–{self.datum_do} ({self.typ})'


class Zakaznik(models.Model):
    salon = models.ForeignKey(Salon, related_name='zakaznici', on_delete=models.CASCADE)
    nick = models.CharField('přezdívka', max_length=100)
    email = models.EmailField('e-mail')
    email_hash = models.CharField('hash e-mailu', max_length=64, blank=True, db_index=True)
    gdpr_souhlas = models.BooleanField('potvrzení seznámení se zásadami', default=False)
    gdpr_datum = models.DateTimeField('datum potvrzení zásad', null=True, blank=True)
    gdpr_zasady_verze = models.CharField('verze zásad GDPR', max_length=20, blank=True)
    gdpr_ip = models.GenericIPAddressField('IP při potvrzení zásad', null=True, blank=True)
    marketing_souhlas = models.BooleanField('marketing souhlas', default=False)
    password_hash = models.CharField('heslo (hash)', max_length=128, blank=True)
    blokovan = models.BooleanField('blokován', default=False)
    no_show_pocet = models.PositiveIntegerField('počet no-show', default=0)
    vytvoreno = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'zákazník'
        verbose_name_plural = 'zákazníci'
        unique_together = ['salon', 'email']
        ordering = ['-vytvoreno']

    def __str__(self):
        return f'{self.nick} ({self.email})'

    def set_password(self, raw_password):
        self.password_hash = make_password(raw_password)

    def check_password(self, raw_password):
        if not self.password_hash:
            return False
        return check_password(raw_password, self.password_hash)

    @property
    def ma_heslo(self):
        return bool(self.password_hash)


class ZakaznikSession(models.Model):
    zakaznik = models.ForeignKey(Zakaznik, related_name='sessiony', on_delete=models.CASCADE)
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    vytvoreno = models.DateTimeField(auto_now_add=True)
    expirace = models.DateTimeField()

    class Meta:
        verbose_name = 'session zákazníka'
        verbose_name_plural = 'sessiony zákazníků'

    def je_platna(self):
        return timezone.now() < self.expirace


class OpakovanaRezervace(models.Model):
    salon = models.ForeignKey(Salon, related_name='opakovane', on_delete=models.CASCADE)
    zakaznik = models.ForeignKey(Zakaznik, on_delete=models.CASCADE)
    zamestnanec = models.ForeignKey(
        Zamestnanec, null=True, blank=True, on_delete=models.SET_NULL,
    )
    interval_tydnu = models.PositiveIntegerField('interval (týdny)', default=6)
    dalsi_termin = models.DateTimeField('další termín')
    aktivni = models.BooleanField(default=True)
    poznamka = models.TextField(blank=True)
    sluzby_ids = models.JSONField('ID služeb', default=list)

    class Meta:
        verbose_name = 'opakovaná rezervace'
        verbose_name_plural = 'opakované rezervace'


class ActiveRezervaceManager(models.Manager):
    """Rezervace viditelné v provozu (nesmazané)."""

    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class Rezervace(models.Model):
    salon = models.ForeignKey(Salon, related_name='rezervace', on_delete=models.CASCADE)
    zakaznik = models.ForeignKey(Zakaznik, null=True, blank=True, on_delete=models.SET_NULL)
    zamestnanec = models.ForeignKey(
        Zamestnanec, null=True, blank=True, on_delete=models.SET_NULL,
        help_text='Prázdné = kdokoliv',
    )
    zacatek = models.DateTimeField('začátek')
    konec = models.DateTimeField('konec')
    stav = models.CharField('stav', max_length=20, choices=STAV_REZERVACE, default='ceka')
    poznamka_zakaznika = models.TextField('poznámka zákazníka', blank=True)
    poznamka_interni = models.TextField('interní poznámka', blank=True)
    typ_vytvoreni = models.CharField('typ vytvoření', max_length=20, choices=TYP_VYTVORENI, default='online')
    cancel_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    potvrzeni_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    potvrzeni_exspirace = models.DateTimeField('potvrzení do', null=True, blank=True)
    opakovana = models.ForeignKey(
        OpakovanaRezervace, null=True, blank=True, on_delete=models.SET_NULL,
    )
    skutecna_delka_minut = models.PositiveIntegerField(null=True, blank=True)
    dokonceno_at = models.DateTimeField(null=True, blank=True)
    notifikace_odeslane = models.JSONField('odeslané notifikace (id)', default=list)
    vytvoreno = models.DateTimeField(auto_now_add=True)
    aktualizovano = models.DateTimeField(auto_now=True)

    # Kontaktní údaje pro rezervace bez účtu
    jmeno_host = models.CharField('jméno (host)', max_length=100, blank=True)
    email_host = models.EmailField('e-mail (host)', blank=True)

    # Životní cyklus dat (řízeno cronem rezervace_zivotni_cyklus)
    thank_you_sent_at = models.DateTimeField('děkovný e-mail odeslán', null=True, blank=True)
    anonymized_at = models.DateTimeField('anonymizováno kdy', null=True, blank=True)
    deleted_at = models.DateTimeField('smazáno z provozu', null=True, blank=True)

    objects = ActiveRezervaceManager()
    all_objects = models.Manager()

    class Meta:
        verbose_name = 'rezervace'
        verbose_name_plural = 'rezervace'
        ordering = ['zacatek']

    def __str__(self):
        return f'{self.zacatek:%d.%m.%Y %H:%M} – {self.get_stav_display()}'

    @property
    def anonymizovano(self):
        return self.anonymized_at is not None

    @property
    def kontaktni_email(self):
        if self.anonymized_at:
            return ''
        if self.zakaznik:
            return self.zakaznik.email
        return self.email_host

    @property
    def kontaktni_jmeno(self):
        if self.zakaznik:
            return self.zakaznik.nick
        return self.jmeno_host or 'Host'


class NoShowZaznam(models.Model):
    """Archiv zákazníků, kteří nedorazili na rezervaci."""
    salon = models.ForeignKey(Salon, related_name='no_show_zaznamy', on_delete=models.CASCADE)
    rezervace = models.ForeignKey(
        Rezervace, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='no_show_zaznam',
    )
    zakaznik = models.ForeignKey(
        Zakaznik, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='no_show_zaznamy',
    )
    jmeno = models.CharField('jméno', max_length=100)
    email = models.EmailField('e-mail', blank=True)
    email_hash = models.CharField('hash e-mailu', max_length=64, blank=True, db_index=True)
    zacatek = models.DateTimeField('termín rezervace')
    zamestnanec_jmeno = models.CharField('pracovník', max_length=100, blank=True)
    sluzby = models.CharField('služby', max_length=500, blank=True)
    email_upozorneni_odeslan = models.BooleanField('upozornění odesláno', default=False)
    zakaznik_blokovan = models.BooleanField('zákazník zablokován', default=False)
    vytvoreno = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'no-show záznam'
        verbose_name_plural = 'no-show archiv'
        ordering = ['-vytvoreno']

    def __str__(self):
        return f'{self.jmeno} – {self.zacatek:%d.%m.%Y %H:%M}'


class RezervaceSluzba(models.Model):
    rezervace = models.ForeignKey(Rezervace, related_name='polozky', on_delete=models.CASCADE)
    sluzba = models.ForeignKey(CenikPolozka, on_delete=models.PROTECT)
    poradi = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'služba rezervace'
        verbose_name_plural = 'služby rezervace'
        ordering = ['poradi']


class BlokaceCasu(models.Model):
    salon = models.ForeignKey(Salon, related_name='blokace', on_delete=models.CASCADE)
    zamestnanec = models.ForeignKey(
        Zamestnanec, null=True, blank=True, on_delete=models.CASCADE,
        help_text='Prázdné = celý salon',
    )
    zacatek = models.DateTimeField('začátek')
    konec = models.DateTimeField('konec')
    popis = models.CharField('popis', max_length=200, blank=True)

    class Meta:
        verbose_name = 'blokace času'
        verbose_name_plural = 'blokace času'
        ordering = ['zacatek']

    def __str__(self):
        return f'{self.popis or "Blokace"} {self.zacatek:%d.%m.%H:%M}'


class RezervaceHistorie(models.Model):
    rezervace = models.ForeignKey(Rezervace, related_name='historie', on_delete=models.CASCADE)
    kdo = models.CharField('kdo', max_length=100)
    kdy = models.DateTimeField(auto_now_add=True)
    popis = models.TextField('popis změny')
    data_pred = models.JSONField(null=True, blank=True)
    data_po = models.JSONField(null=True, blank=True)

    class Meta:
        verbose_name = 'historie rezervace'
        verbose_name_plural = 'historie rezervací'
        ordering = ['-kdy']


class SalonAuditLog(models.Model):
    """Audit log všech změn v salonu (rezervace, ceník, personál, nastavení…)."""
    salon = models.ForeignKey(Salon, related_name='audit_log', on_delete=models.CASCADE)
    kdo = models.CharField('kdo', max_length=100)
    kdy = models.DateTimeField(auto_now_add=True)
    kategorie = models.CharField('kategorie', max_length=50)
    popis = models.TextField('popis')
    objekt_typ = models.CharField('typ objektu', max_length=50, blank=True)
    objekt_id = models.IntegerField(null=True, blank=True)
    data_pred = models.JSONField(null=True, blank=True)
    data_po = models.JSONField(null=True, blank=True)

    class Meta:
        verbose_name = 'audit log'
        verbose_name_plural = 'audit log'
        ordering = ['-kdy']

    def __str__(self):
        return f'{self.kdy:%d.%m.%Y %H:%M} — {self.kdo}: {self.popis[:60]}'


class SouhlasGDPR(models.Model):
    """Důkazní záznam o potvrzení Zásad ochrany osobních údajů."""

    TYP_REZERVACE = 'rezervace'
    TYP_REGISTRACE = 'registrace'
    TYPY = [
        (TYP_REZERVACE, 'Online rezervace'),
        (TYP_REGISTRACE, 'Registrace účtu'),
    ]

    salon = models.ForeignKey(Salon, related_name='souhlasy_gdpr', on_delete=models.CASCADE)
    zakaznik = models.ForeignKey(
        'Zakaznik', null=True, blank=True, on_delete=models.SET_NULL, related_name='souhlasy_gdpr',
    )
    rezervace = models.ForeignKey(
        'Rezervace', null=True, blank=True, on_delete=models.SET_NULL, related_name='souhlasy_gdpr',
    )
    email = models.EmailField('e-mail', blank=True)
    typ = models.CharField('typ', max_length=20, choices=TYPY)
    zasady_verze = models.CharField('verze zásad', max_length=20)
    jazyk = models.CharField('jazyk', max_length=10, default='cs')
    ip_adresa = models.GenericIPAddressField('IP adresa', null=True, blank=True)
    user_agent = models.CharField('user-agent', max_length=300, blank=True)
    vytvoreno = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'potvrzení seznámení se zásadami'
        verbose_name_plural = 'potvrzení seznámení se zásadami'
        ordering = ['-vytvoreno']

    def __str__(self):
        return f'{self.get_typ_display()} — {self.zasady_verze} — {self.vytvoreno:%d.%m.%Y %H:%M}'
