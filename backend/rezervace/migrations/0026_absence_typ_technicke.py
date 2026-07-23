from django.db import migrations, models


def migrate_volno_to_dovolena(apps, schema_editor):
    ZamestnanecAbsence = apps.get_model('rezervace', 'ZamestnanecAbsence')
    ZamestnanecAbsence.objects.filter(typ='volno').update(typ='dovolena')


class Migration(migrations.Migration):

    dependencies = [
        ('rezervace', '0025_notifikace_storno'),
    ]

    operations = [
        migrations.RunPython(migrate_volno_to_dovolena, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='zamestnanecabsence',
            name='typ',
            field=models.CharField(
                choices=[
                    ('dovolena', 'Dovolená'),
                    ('nemoc', 'Nemoc'),
                    ('technicke', 'Technické problémy'),
                ],
                default='dovolena',
                max_length=20,
                verbose_name='typ',
            ),
        ),
    ]
