from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rezervace', '0012_notifikace_platba'),
    ]

    operations = [
        migrations.AddField(
            model_name='zamestnanec',
            name='cislo_uctu',
            field=models.CharField(blank=True, max_length=34, verbose_name='číslo účtu'),
        ),
    ]
