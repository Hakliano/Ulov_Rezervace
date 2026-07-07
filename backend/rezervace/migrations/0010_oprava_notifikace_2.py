from django.db import migrations


def oprav_notifikace_2(apps, schema_editor):
    from rezervace.notifikace_defaults import dopln_na_tri

    RezervacniNastaveni = apps.get_model('rezervace', 'RezervacniNastaveni')
    for nastaveni in RezervacniNastaveni.objects.all():
        opravene = dopln_na_tri(nastaveni.notifikace)
        if opravene != nastaveni.notifikace:
            nastaveni.notifikace = opravene
            nastaveni.save(update_fields=['notifikace'])


class Migration(migrations.Migration):

    dependencies = [
        ('rezervace', '0009_noshowzaznam'),
    ]

    operations = [
        migrations.RunPython(oprav_notifikace_2, migrations.RunPython.noop),
    ]
