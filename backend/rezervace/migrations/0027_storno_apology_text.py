from django.db import migrations

from rezervace.notifikace_defaults import (
    DEFAULT_PREDMET_STORNO,
    DEFAULT_TEXT_STORNO,
    MANUAL_TYP_STORNO,
    dopln_na_notifikace,
)


OLD_SNIPPETS = (
    'Vaše rezervace v salonu',
    'byla zrušena',
    'Storno rezervace –',
)


def refresh_storno_apology(apps, schema_editor):
    RezervacniNastaveni = apps.get_model('rezervace', 'RezervacniNastaveni')
    for nastaveni in RezervacniNastaveni.objects.all():
        items = dopln_na_notifikace(nastaveni.notifikace)
        changed = False
        for n in items:
            if n.get('manual_typ') != MANUAL_TYP_STORNO:
                continue
            text = n.get('text') or ''
            predmet = n.get('predmet') or ''
            if 'velice se omlouváme' in text:
                continue
            looks_old = (
                any(s in text for s in OLD_SNIPPETS)
                or predmet.startswith('Storno rezervace')
            )
            if looks_old:
                n['predmet'] = DEFAULT_PREDMET_STORNO
                n['text'] = DEFAULT_TEXT_STORNO
                changed = True
        if changed:
            nastaveni.notifikace = items
            nastaveni.save(update_fields=['notifikace'])


class Migration(migrations.Migration):

    dependencies = [
        ('rezervace', '0026_absence_typ_technicke'),
    ]

    operations = [
        migrations.RunPython(refresh_storno_apology, migrations.RunPython.noop),
    ]
