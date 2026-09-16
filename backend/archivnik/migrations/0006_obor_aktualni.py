from django.db import migrations, models


def backfill_aktualni(apps, schema_editor):
    Obor = apps.get_model('archivnik', 'Obor')
    for salon_id in Obor.objects.values_list('salon_id', flat=True).distinct():
        if Obor.objects.filter(salon_id=salon_id, aktualni=True).exists():
            continue
        prvni = Obor.objects.filter(salon_id=salon_id).order_by('poradi', 'id').first()
        if prvni:
            Obor.objects.filter(pk=prvni.pk).update(aktualni=True)


def unset_aktualni(apps, schema_editor):
    Obor = apps.get_model('archivnik', 'Obor')
    Obor.objects.filter(aktualni=True).update(aktualni=False)


class Migration(migrations.Migration):

    dependencies = [
        ('archivnik', '0005_p3_lock_and_terminology'),
    ]

    operations = [
        migrations.AddField(
            model_name='obor',
            name='aktualni',
            field=models.BooleanField(default=False),
        ),
        migrations.AddConstraint(
            model_name='obor',
            constraint=models.UniqueConstraint(
                condition=models.Q(('aktualni', True)),
                fields=('salon',),
                name='archivnik_obor_salon_jeden_aktualni',
            ),
        ),
        migrations.RunPython(backfill_aktualni, unset_aktualni),
    ]
