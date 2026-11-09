from django.conf import settings
from django.db import models


class Profil(models.Model):
    """Volitelná fotografie k účtu Django. Hesla tu nejsou."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profil',
    )
    foto = models.FileField('profilová fotografie', upload_to='profil/', blank=True)
    telefon = models.CharField('telefon', max_length=40, blank=True, default='')
    vyzadovat_zmenu_hesla = models.BooleanField(
        'po přihlášení vynutit změnu hesla',
        default=False,
    )

    class Meta:
        verbose_name = 'profil'
        verbose_name_plural = 'profily'

    def __str__(self):
        return self.user.get_username()


class EmailSchranka(models.Model):
    PROJEKT_MODERNIK = 'modernik'
    PROJEKT_HYA = 'hereyouare'
    PROJEKTY = [
        (PROJEKT_MODERNIK, 'Moderník'),
        (PROJEKT_HYA, 'HereYouAre'),
    ]

    STAV_NEZKOU = 'nezkouseno'
    STAV_OK = 'ok'
    STAV_CHYBA = 'chyba'
    STAVY = [
        (STAV_NEZKOU, 'Nezkoušeno'),
        (STAV_OK, 'Připojeno'),
        (STAV_CHYBA, 'Chyba'),
    ]

    email = models.EmailField('e-mailová adresa', unique=True)
    projekt = models.CharField('projekt', max_length=20, choices=PROJEKTY, db_index=True)
    prihlasovaci_jmeno = models.CharField('přihlašovací jméno', max_length=200)
    heslo_sifra = models.TextField('heslo (šifrované)', blank=True, default='')
    podpis_html = models.TextField('HTML podpis', blank=True, default='')

    imap_host = models.CharField(max_length=200, default='imap.forpsi.com')
    imap_port = models.PositiveIntegerField(default=993)
    imap_ssl = models.BooleanField(default=True)

    smtp_host = models.CharField(max_length=200, default='smtp.forpsi.com')
    smtp_port = models.PositiveIntegerField(default=465)
    smtp_ssl = models.BooleanField(default=True)
    smtp_starttls = models.BooleanField(default=False)

    test_stav = models.CharField(max_length=12, choices=STAVY, default=STAV_NEZKOU)
    test_info = models.CharField(max_length=300, blank=True, default='')
    testovano = models.DateTimeField(null=True, blank=True)

    uzivatele = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='email_schranky',
        blank=True,
        verbose_name='přidělení uživatelé',
    )

    vytvoreno = models.DateTimeField(auto_now_add=True)
    upraveno = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'e-mailová schránka'
        verbose_name_plural = 'e-mailové schránky'
        ordering = ['email']

    def __str__(self):
        return self.email

    @property
    def ma_heslo(self):
        return bool((self.heslo_sifra or '').strip())


class PoznamkaKoncept(models.Model):
    """Soukromá poznámka nebo koncept — vázaná na jednoho uživatele."""

    vlastnik = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='poznamky_koncepty',
    )
    nazev = models.CharField('název', max_length=200)
    poradi = models.IntegerField('pořadí', default=0)
    obsah_html = models.TextField('obsah (HTML)', blank=True, default='')
    vytvoreno = models.DateTimeField(auto_now_add=True)
    upraveno = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'poznámka / koncept'
        verbose_name_plural = 'poznámky a koncepty'
        ordering = ['poradi', '-upraveno']

    def __str__(self):
        return self.nazev


def _koncept_upload(instance, filename):
    safe = (filename or 'priloha').replace('\\', '_').split('/')[-1]
    return f'koncepty/{instance.koncept.vlastnik_id}/{instance.koncept_id}/{safe}'


class EmailKoncept(models.Model):
    """Rozepsaný e-mail — pouze v Pošťáku, bez FORPSI."""

    vlastnik = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='email_koncepty',
    )
    schranka = models.ForeignKey(
        EmailSchranka,
        on_delete=models.CASCADE,
        related_name='koncepty',
    )
    komu = models.TextField('komu', blank=True, default='')
    kopie = models.TextField('kopie', blank=True, default='')
    skryte = models.TextField('skrytá kopie', blank=True, default='')
    predmet = models.CharField('předmět', max_length=500, blank=True, default='')
    telo_html = models.TextField('tělo (HTML)', blank=True, default='')
    in_reply_to = models.CharField(max_length=300, blank=True, default='')
    vytvoreno = models.DateTimeField(auto_now_add=True)
    upraveno = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'koncept e-mailu'
        verbose_name_plural = 'koncepty e-mailů'
        ordering = ['-upraveno']

    def __str__(self):
        return self.predmet or f'Koncept #{self.pk}'


class EmailKonceptPriloha(models.Model):
    """Přílohy konceptů — zahrnout do budoucí zálohy Pošťáka spolu s dokumentací."""

    koncept = models.ForeignKey(
        EmailKoncept,
        on_delete=models.CASCADE,
        related_name='prilohy',
    )
    soubor = models.FileField(upload_to=_koncept_upload)
    nazev = models.CharField(max_length=255)
    content_type = models.CharField(max_length=120, default='application/octet-stream')
    velikost = models.PositiveIntegerField(default=0)
    vytvoreno = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'příloha konceptu'
        verbose_name_plural = 'přílohy konceptu'


from .chat_models import ChatZprava  # noqa: E402,F401
from .kalendar_models import KalendarUdalost  # noqa: E402,F401
from .klienti_models import KlientHya, KlientModernik, KlientSektor, KlientStavHistorie, KlientSyncMeta  # noqa: E402,F401
from .dokumentace_models import DokumentSlozka, DokumentSoubor  # noqa: E402,F401
from .user_credentials_models import OdeslaniPrihlasovacich  # noqa: E402,F401
