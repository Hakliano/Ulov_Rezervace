from django.db import migrations

# Interní dema (salon 1–17). Ostré provozovny (Franek 18, Kudrlinka 19, …) ne.
DEMO_SALON_IDS = tuple(range(1, 18))


def odznac_ostre_partnery(apps, schema_editor):
    PartnerNastaveni = apps.get_model('partner_admin', 'PartnerNastaveni')
    PartnerNastaveni.objects.exclude(salon_id__in=DEMO_SALON_IDS).update(je_testovaci=False)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('partner_admin', '0012_vychozi_variabilni_symbol'),
    ]

    operations = [
        migrations.RunPython(odznac_ostre_partnery, noop_reverse),
    ]
