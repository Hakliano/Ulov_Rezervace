from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('salons', '0004_cenikpolozka_aktivni_cenikpolozka_delka_minut_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='cenikpolozka',
            name='obrazek',
            field=models.URLField(blank=True, max_length=500, verbose_name='obrázek služby (URL)'),
        ),
    ]
