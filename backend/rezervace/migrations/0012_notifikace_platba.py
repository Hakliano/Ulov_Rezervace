from django.db import migrations

from rezervace.notifikace_defaults import dopln_na_notifikace


def dopln_ctvrtou_notifikaci(apps, schema_editor):
    RezervacniNastaveni = apps.get_model('rezervace', 'RezervacniNastaveni')
    for nastaveni in RezervacniNastaveni.objects.all():
        notifikace = dopln_na_notifikace(nastaveni.notifikace)
        if len(notifikace) >= 4:
            nastaveni.notifikace = notifikace
            nastaveni.save(update_fields=['notifikace'])


class Migration(migrations.Migration):

    dependencies = [
        ('rezervace', '0011_noshow_email_text'),
    ]

    operations = [
        migrations.RunPython(dopln_ctvrtou_notifikaci, migrations.RunPython.noop),
    ]
