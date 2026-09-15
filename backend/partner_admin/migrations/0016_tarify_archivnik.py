from decimal import Decimal

from django.db import migrations


NOVY_TARIFY = [
    ('Archivník', 6),
    ('Moderník + Archivník', 7),
    ('Materiálník + Archivník', 8),
    ('Moderník + Materiálník + Archivník', 9),
]


def seed_tarify_archivnik(apps, schema_editor):
    PartnerTarif = apps.get_model('partner_admin', 'PartnerTarif')
    for nazev, razeni in NOVY_TARIFY:
        PartnerTarif.objects.get_or_create(
            nazev=nazev,
            defaults={'castka': Decimal('0.00'), 'razeni': razeni, 'aktivni': True},
        )


def unseed_tarify_archivnik(apps, schema_editor):
    PartnerTarif = apps.get_model('partner_admin', 'PartnerTarif')
    PartnerTarif.objects.filter(nazev__in=[nazev for nazev, _ in NOVY_TARIFY]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('partner_admin', '0015_modul_archivnik'),
    ]

    operations = [
        migrations.RunPython(seed_tarify_archivnik, unseed_tarify_archivnik),
    ]
