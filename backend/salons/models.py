from django.db import models


class Salon(models.Model):
    name = models.CharField('název', max_length=200)
    description = models.TextField('popis', blank=True)
    address = models.CharField('adresa', max_length=300, blank=True)
    phone = models.CharField('telefon', max_length=50, blank=True)
    email = models.EmailField('e-mail', blank=True)
    hero_image = models.URLField('úvodní fotka (URL)', blank=True, max_length=500)
    logo_url = models.URLField('logo (URL)', blank=True, max_length=500)
    favicon_url = models.URLField('favicon (URL)', blank=True, max_length=500)
    primary_color = models.CharField('primární barva (#RRGGBB)', max_length=7, blank=True)
    accent_color = models.CharField('akcentová barva (#RRGGBB)', max_length=7, blank=True)

    class Meta:
        verbose_name = 'salon'
        verbose_name_plural = 'salony'

    def __str__(self):
        return self.name


class CenikPolozka(models.Model):
    salon = models.ForeignKey(
        Salon, related_name='cenik', on_delete=models.CASCADE, verbose_name='salon'
    )
    nazev = models.CharField('název služby', max_length=200)
    cena = models.DecimalField('cena (Kč)', max_digits=10, decimal_places=0)
    obrazek = models.URLField('obrázek služby (URL)', blank=True, max_length=500)
    poradi = models.PositiveIntegerField('pořadí', default=0)
    delka_minut = models.PositiveIntegerField('délka služby (min)', default=30)
    rezerva_minut = models.PositiveIntegerField('časová rezerva po službě (min)', default=0)
    aktivni = models.BooleanField('aktivní pro rezervace', default=True)

    class Meta:
        verbose_name = 'položka ceníku'
        verbose_name_plural = 'položky ceníku'
        ordering = ['poradi', 'id']

    def __str__(self):
        return f'{self.nazev} – {self.cena} Kč'


class Novinka(models.Model):
    salon = models.ForeignKey(
        Salon, related_name='novinky', on_delete=models.CASCADE, verbose_name='salon'
    )
    nadpis = models.CharField('nadpis', max_length=200)
    text = models.TextField('text')
    obrazek = models.URLField('obrázek (URL)', blank=True, max_length=500)
    datum = models.DateField('datum', auto_now_add=True)

    class Meta:
        verbose_name = 'novinka'
        verbose_name_plural = 'novinky'
        ordering = ['-datum', '-id']

    def __str__(self):
        return self.nadpis


class OteviraciDoba(models.Model):
    DENY = [
        (0, 'Pondělí'),
        (1, 'Úterý'),
        (2, 'Středa'),
        (3, 'Čtvrtek'),
        (4, 'Pátek'),
        (5, 'Sobota'),
        (6, 'Neděle'),
    ]

    salon = models.ForeignKey(
        Salon, related_name='oteviraci_doba', on_delete=models.CASCADE, verbose_name='salon'
    )
    den = models.IntegerField('den', choices=DENY)
    od = models.TimeField('od', null=True, blank=True)
    do = models.TimeField('do', null=True, blank=True)
    zavreno = models.BooleanField('zavřeno', default=False)

    class Meta:
        verbose_name = 'otevírací doba'
        verbose_name_plural = 'otevírací doby'
        ordering = ['den']
        unique_together = ['salon', 'den']

    def __str__(self):
        if self.zavreno:
            return f'{self.get_den_display()} – zavřeno'
        return f'{self.get_den_display()} {self.od}–{self.do}'


class SalonObrazek(models.Model):
    salon = models.ForeignKey(
        Salon, related_name='obrazky', on_delete=models.CASCADE, verbose_name='salon'
    )
    url = models.URLField('URL obrázku', max_length=500)
    popis = models.CharField('popis', max_length=200, blank=True)
    poradi = models.PositiveIntegerField('pořadí', default=0)

    class Meta:
        verbose_name = 'obrázek'
        verbose_name_plural = 'obrázky'
        ordering = ['poradi', 'id']

    def __str__(self):
        return self.popis or self.url.split('/')[-1]
