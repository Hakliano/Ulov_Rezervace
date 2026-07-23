from django.db import migrations


def create_partner_settings(apps, schema_editor):
    Salon = apps.get_model('salons', 'Salon')
    PartnerNastaveni = apps.get_model('partner_admin', 'PartnerNastaveni')
    for salon in Salon.objects.all():
        PartnerNastaveni.objects.get_or_create(
            salon_id=salon.id,
            defaults={'fakturacni_email': salon.email},
        )


def remove_partner_settings(apps, schema_editor):
    PartnerNastaveni = apps.get_model('partner_admin', 'PartnerNastaveni')
    PartnerNastaveni.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ('partner_admin', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_partner_settings, remove_partner_settings),
    ]
