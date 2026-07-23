from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('salons', '0006_salon_branding'),
    ]

    operations = [
        migrations.AddField(
            model_name='salon',
            name='banner_text',
            field=models.CharField(blank=True, max_length=300, verbose_name='banner text'),
        ),
        migrations.AddField(
            model_name='salon',
            name='banner_od',
            field=models.DateField(blank=True, null=True, verbose_name='banner od'),
        ),
        migrations.AddField(
            model_name='salon',
            name='banner_do',
            field=models.DateField(blank=True, null=True, verbose_name='banner do'),
        ),
        migrations.AddField(
            model_name='salon',
            name='banner_enabled',
            field=models.BooleanField(default=False, verbose_name='banner zapnutý'),
        ),
    ]
