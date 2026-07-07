from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rezervace', '0007_zamestnanec_fotka_zamestnanec_popis_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='rezervacninastaveni',
            name='recenze_url',
            field=models.URLField(
                blank=True,
                default='',
                help_text='Odkaz na recenze (Google, Facebook…). Použijte v e-mailu jako {{ recenze_url }}.',
                verbose_name='URL recenze',
            ),
        ),
    ]
