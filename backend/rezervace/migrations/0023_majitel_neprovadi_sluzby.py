from django.db import migrations


def uprav_majitele(apps, schema_editor):
    Zamestnanec = apps.get_model('rezervace', 'Zamestnanec')
    ZamestnanecRozvrh = apps.get_model('rezervace', 'ZamestnanecRozvrh')

    for z in Zamestnanec.objects.filter(role='majitel'):
        if z.zobrazit_na_webu:
            z.zobrazit_na_webu = False
            z.save(update_fields=['zobrazit_na_webu'])
        for den in range(7):
            ZamestnanecRozvrh.objects.update_or_create(
                zamestnanec=z,
                den=den,
                defaults={'volno': True, 'od': None, 'do': None},
            )


class Migration(migrations.Migration):

    dependencies = [
        ('rezervace', '0022_remove_salon_retention_config'),
    ]

    operations = [
        migrations.RunPython(uprav_majitele, migrations.RunPython.noop),
    ]
