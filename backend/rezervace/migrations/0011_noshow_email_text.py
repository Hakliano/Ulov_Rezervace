from django.db import migrations

from rezervace.notifikace_defaults import DEFAULT_TEXT_NO_SHOW, dopln_na_tri


def aktualizuj_noshow_text(apps, schema_editor):
    RezervacniNastaveni = apps.get_model('rezervace', 'RezervacniNastaveni')
    stary_uvod = 'zaznamenali jsme, že jste se nedostavili'
    for nastaveni in RezervacniNastaveni.objects.all():
        notifikace = dopln_na_tri(nastaveni.notifikace)
        zmeneno = False
        for n in notifikace:
            if n.get('manual') or n.get('offset') == 'manual':
                text = n.get('text') or ''
                if stary_uvod in text and 'problematický' not in text:
                    n['text'] = DEFAULT_TEXT_NO_SHOW
                    zmeneno = True
        if zmeneno:
            nastaveni.notifikace = notifikace
            nastaveni.save(update_fields=['notifikace'])


class Migration(migrations.Migration):

    dependencies = [
        ('rezervace', '0010_oprava_notifikace_2'),
    ]

    operations = [
        migrations.RunPython(aktualizuj_noshow_text, migrations.RunPython.noop),
    ]
