from django.db import migrations

from rezervace.notifikace_defaults import dopln_na_notifikace


def dopln_storno_notifikaci(apps, schema_editor):
    RezervacniNastaveni = apps.get_model('rezervace', 'RezervacniNastaveni')
    for nastaveni in RezervacniNastaveni.objects.all():
        notifikace = dopln_na_notifikace(nastaveni.notifikace)
        if len(notifikace) >= 5:
            nastaveni.notifikace = notifikace
            nastaveni.save(update_fields=['notifikace'])


class Migration(migrations.Migration):

    dependencies = [
        ('rezervace', '0024_rezervace_salon_indexes'),
    ]

    operations = [
        migrations.RunPython(dopln_storno_notifikaci, migrations.RunPython.noop),
    ]
