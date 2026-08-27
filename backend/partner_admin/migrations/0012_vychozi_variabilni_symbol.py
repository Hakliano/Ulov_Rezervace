from django.db import migrations


def nastavit_vs_80_id(apps, schema_editor):
    PartnerNastaveni = apps.get_model('partner_admin', 'PartnerNastaveni')
    PartnerNastaveni.objects.update(variabilni_symbol=None)
    for partner in PartnerNastaveni.objects.all().iterator():
        partner.variabilni_symbol = f'80{partner.salon_id}'
        partner.save(update_fields=['variabilni_symbol'])


def vratit_prazdne_vs(apps, schema_editor):
    PartnerNastaveni = apps.get_model('partner_admin', 'PartnerNastaveni')
    PartnerNastaveni.objects.update(variabilni_symbol=None)


class Migration(migrations.Migration):

    dependencies = [
        ('partner_admin', '0011_kam_provize_faktura'),
    ]

    operations = [
        migrations.RunPython(nastavit_vs_80_id, vratit_prazdne_vs),
    ]
