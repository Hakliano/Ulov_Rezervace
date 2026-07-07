from django.db import migrations, models


def prenes_stavy(apps, schema_editor):
    Rezervace = apps.get_model('rezervace', 'Rezervace')
    for r in Rezervace.objects.filter(anonymizovano=True):
        r.anonymized_at = r.anonymizovano_at
        r.save(update_fields=['anonymized_at'])


def prenes_dekujici(apps, schema_editor):
    from datetime import timedelta

    Rezervace = apps.get_model('rezervace', 'Rezervace')
    for r in Rezervace.objects.filter(stav='dokonceno'):
        odeslane = r.notifikace_odeslane or []
        if not odeslane:
            continue
        for nid in odeslane:
            if nid and str(nid) != 'manual':
                r.thank_you_sent_at = r.dokonceno_at or (r.konec + timedelta(hours=2))
                r.save(update_fields=['thank_you_sent_at'])
                break


class Migration(migrations.Migration):

    dependencies = [
        ('rezervace', '0016_salon_audit_log'),
    ]

    operations = [
        migrations.AddField(
            model_name='rezervace',
            name='thank_you_sent_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='děkovný e-mail odeslán'),
        ),
        migrations.AddField(
            model_name='rezervace',
            name='anonymized_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='anonymizováno kdy'),
        ),
        migrations.AddField(
            model_name='rezervace',
            name='deleted_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='smazáno z provozu'),
        ),
        migrations.RunPython(prenes_stavy, migrations.RunPython.noop),
        migrations.RunPython(prenes_dekujici, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='rezervace',
            name='anonymizovano',
        ),
        migrations.RemoveField(
            model_name='rezervace',
            name='anonymizovano_at',
        ),
    ]
