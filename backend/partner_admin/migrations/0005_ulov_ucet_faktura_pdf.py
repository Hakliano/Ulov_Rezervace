from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('partner_admin', '0004_upozorneniplatby_text'),
    ]

    operations = [
        migrations.AddField(
            model_name='partnernastaveni',
            name='ulov_cislo_uctu',
            field=models.CharField(
                blank=True,
                help_text='Číslo účtu ULOV ve formátu číslo/kód banky nebo IBAN. Není to účet personálu.',
                max_length=34,
                verbose_name='účet ULOV (pro QR / převod)',
            ),
        ),
        migrations.AddField(
            model_name='platbapartnera',
            name='faktura_pdf',
            field=models.FileField(
                blank=True,
                null=True,
                upload_to='partner_faktury/%Y/%m/',
                verbose_name='faktura PDF',
            ),
        ),
    ]
