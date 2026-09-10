from django.db import migrations


def wipe_smtp_passwords(apps, schema_editor):
    RezervacniNastaveni = apps.get_model('rezervace', 'RezervacniNastaveni')
    RezervacniNastaveni.objects.exclude(smtp_password='').update(smtp_password='')


def noop_reverse(apps, schema_editor):
    return


class Migration(migrations.Migration):

    dependencies = [
        ('rezervace', '0034_encrypt_smtp_password'),
    ]

    operations = [
        migrations.RunPython(wipe_smtp_passwords, noop_reverse),
    ]
