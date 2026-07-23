from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('salons', '0005_cenikpolozka_obrazek'),
    ]

    operations = [
        migrations.AddField(
            model_name='salon',
            name='logo_url',
            field=models.URLField(blank=True, max_length=500, verbose_name='logo (URL)'),
        ),
        migrations.AddField(
            model_name='salon',
            name='favicon_url',
            field=models.URLField(blank=True, max_length=500, verbose_name='favicon (URL)'),
        ),
        migrations.AddField(
            model_name='salon',
            name='primary_color',
            field=models.CharField(blank=True, max_length=7, verbose_name='primární barva (#RRGGBB)'),
        ),
        migrations.AddField(
            model_name='salon',
            name='accent_color',
            field=models.CharField(blank=True, max_length=7, verbose_name='akcentová barva (#RRGGBB)'),
        ),
    ]
