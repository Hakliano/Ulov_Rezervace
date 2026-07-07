from django.db import migrations

from rezervace.notifikace_defaults import DEFAULT_TEXT_NO_SHOW, dopln_na_notifikace


def oprav_noshow_text_gdpr(apps, schema_editor):
    RezervacniNastaveni = apps.get_model('rezervace', 'RezervacniNastaveni')
    stary_uvod = 'společný rezervační systém'
    for nastaveni in RezervacniNastaveni.objects.all():
        notifikace = dopln_na_notifikace(nastaveni.notifikace)
        zmeneno = False
        for n in notifikace:
            if n.get('manual') or n.get('offset') == 'manual':
                text = n.get('text') or ''
                if stary_uvod in text or 'napříč všemi' in text:
                    n['text'] = DEFAULT_TEXT_NO_SHOW
                    zmeneno = True
        if zmeneno:
            nastaveni.notifikace = notifikace
            nastaveni.save(update_fields=['notifikace'])


class Migration(migrations.Migration):

    dependencies = [
        ('rezervace', '0013_zamestnanec_cislo_uctu'),
    ]

    operations = [
        migrations.RunPython(oprav_noshow_text_gdpr, migrations.RunPython.noop),
    ]
