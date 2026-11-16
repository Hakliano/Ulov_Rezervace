from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('partner_admin', '0021_postak_potencialni_api'),
    ]

    operations = [
        migrations.AlterField(
            model_name='potencialnikontakt',
            name='adresa',
            field=models.TextField(blank=True, null=True, verbose_name='adresa'),
        ),
        migrations.AddField(
            model_name='potencialnikontakt',
            name='mesto',
            field=models.CharField(
                blank=True, db_index=True, max_length=120, null=True, verbose_name='město',
            ),
        ),
        migrations.AddField(
            model_name='potencialnikontakt',
            name='cast_obce',
            field=models.CharField(blank=True, max_length=120, null=True, verbose_name='část obce'),
        ),
        migrations.AddField(
            model_name='potencialnikontakt',
            name='latitude',
            field=models.DecimalField(
                blank=True, decimal_places=7, max_digits=10, null=True, verbose_name='latitude',
            ),
        ),
        migrations.AddField(
            model_name='potencialnikontakt',
            name='longitude',
            field=models.DecimalField(
                blank=True, decimal_places=7, max_digits=10, null=True, verbose_name='longitude',
            ),
        ),
    ]