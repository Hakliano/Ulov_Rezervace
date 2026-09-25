from django.db import migrations, models


def nuly_na_null(apps, schema_editor):
    # Dřív prázdná cena šla do DB jako 0. 0 teď znamená Zdarma — staré nuly schovat.
    CenikPolozka = apps.get_model('salons', 'CenikPolozka')
    CenikPolozka.objects.filter(cena=0).update(cena=None)


class Migration(migrations.Migration):

    dependencies = [
        ('salons', '0008_cenikpolozka_rizikovy'),
    ]

    operations = [
        migrations.AddField(
            model_name='cenikpolozka',
            name='popis',
            field=models.TextField(blank=True, verbose_name='popis služby'),
        ),
        migrations.AddField(
            model_name='cenikpolozka',
            name='cena_do',
            field=models.DecimalField(
                blank=True, decimal_places=0, max_digits=10, null=True, verbose_name='cena do (Kč)',
            ),
        ),
        migrations.AddField(
            model_name='cenikpolozka',
            name='zobrazit_od',
            field=models.BooleanField(default=False, verbose_name='na webu napsat Od'),
        ),
        migrations.AlterField(
            model_name='cenikpolozka',
            name='cena',
            field=models.DecimalField(
                blank=True, decimal_places=0, max_digits=10, null=True, verbose_name='cena (Kč)',
            ),
        ),
        migrations.RunPython(nuly_na_null, migrations.RunPython.noop),
    ]
