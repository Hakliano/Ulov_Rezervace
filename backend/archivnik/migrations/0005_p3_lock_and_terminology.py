from django.db import migrations, models


def backfill_preset_lock_and_terms(apps, schema_editor):
    Obor = apps.get_model('archivnik', 'Obor')
    ObjectType = apps.get_model('archivnik', 'ObjectType')
    CustomFieldDef = apps.get_model('archivnik', 'CustomFieldDef')
    from archivnik.presets import PRESETS

    terms = {
        kod: (
            row.get('objekt_jednotne') or 'Objekt',
            row.get('objekt_mnozne') or 'Objekty',
        )
        for kod, row in PRESETS.items()
    }
    catalog_types = {
        kod: {typ['nazev']: {pole['nazev'] for pole in typ['pole']} for typ in row['typy']}
        for kod, row in PRESETS.items()
    }

    for obor in Obor.objects.exclude(zdroj_preset=''):
        jednotne, mnozne = terms.get(obor.zdroj_preset, ('Objekt', 'Objekty'))
        if obor.objekt_jednotne == 'Objekt' and obor.objekt_mnozne == 'Objekty':
            obor.objekt_jednotne = jednotne
            obor.objekt_mnozne = mnozne
            obor.save(update_fields=['objekt_jednotne', 'objekt_mnozne'])
        names = catalog_types.get(obor.zdroj_preset) or {}
        for typ in ObjectType.objects.filter(salon_id=obor.salon_id, obor_id=obor.id):
            if typ.nazev not in names:
                continue
            if not typ.zdroj_preset:
                typ.zdroj_preset = obor.zdroj_preset
                typ.save(update_fields=['zdroj_preset'])
            pole_names = names[typ.nazev]
            CustomFieldDef.objects.filter(
                typ_id=typ.id, nazev__in=pole_names, zdroj_preset='',
            ).update(zdroj_preset=obor.zdroj_preset)

    ObjectType.objects.filter(nazev='Chrup').update(vyzaduje_nazev=False)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('archivnik', '0004_obor_and_field_kinds'),
    ]

    operations = [
        migrations.AddField(
            model_name='obor',
            name='objekt_jednotne',
            field=models.CharField(default='Objekt', max_length=40, verbose_name='jednotné číslo objektu'),
        ),
        migrations.AddField(
            model_name='obor',
            name='objekt_mnozne',
            field=models.CharField(default='Objekty', max_length=40, verbose_name='množné číslo objektu'),
        ),
        migrations.AddField(
            model_name='objecttype',
            name='vyzaduje_nazev',
            field=models.BooleanField(default=True, verbose_name='vyžaduje název objektu'),
        ),
        migrations.AddField(
            model_name='objecttype',
            name='zdroj_preset',
            field=models.CharField(blank=True, default='', max_length=32),
        ),
        migrations.AddField(
            model_name='customfielddef',
            name='zdroj_preset',
            field=models.CharField(blank=True, default='', max_length=32),
        ),
        migrations.AlterField(
            model_name='object',
            name='nazev',
            field=models.CharField(blank=True, default='', max_length=160, verbose_name='název'),
        ),
        migrations.RunPython(backfill_preset_lock_and_terms, noop),
    ]
