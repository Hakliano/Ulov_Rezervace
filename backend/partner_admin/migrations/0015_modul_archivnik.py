from django.db import migrations


def seed_archivnik(apps, schema_editor):
    ModulKatalog = apps.get_model('partner_admin', 'ModulKatalog')
    ModulKatalog.objects.get_or_create(
        kod='archivnik',
        defaults={
            'nazev': 'Archivník',
            'popis': 'Digitální kartotéka. Funguje samostatně, bez FLOW i bez Moderníka.',
            'razeni': 20,
        },
    )


def unseed_archivnik(apps, schema_editor):
    ModulKatalog = apps.get_model('partner_admin', 'ModulKatalog')
    ModulKatalog.objects.filter(kod='archivnik').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('partner_admin', '0014_extra_faktury_vydaje'),
    ]

    operations = [
        migrations.RunPython(seed_archivnik, unseed_archivnik),
    ]
