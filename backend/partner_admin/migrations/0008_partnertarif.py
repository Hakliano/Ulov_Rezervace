from decimal import Decimal

from django.db import migrations, models


VYCHOZI_TARIFY = [
    ('Moderník', 1),
    ('Materiálník', 2),
    ('Moderník + Materiálník', 3),
    ('WEB', 4),
    ('Partnerský web', 5),
]


def seed_tarify(apps, schema_editor):
    PartnerTarif = apps.get_model('partner_admin', 'PartnerTarif')
    for nazev, razeni in VYCHOZI_TARIFY:
        PartnerTarif.objects.get_or_create(
            nazev=nazev,
            defaults={'castka': Decimal('0.00'), 'razeni': razeni, 'aktivni': True},
        )


def unseed_tarify(apps, schema_editor):
    PartnerTarif = apps.get_model('partner_admin', 'PartnerTarif')
    PartnerTarif.objects.filter(nazev__in=[nazev for nazev, _ in VYCHOZI_TARIFY]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('partner_admin', '0007_moduly_tenant_uuid'),
    ]

    operations = [
        migrations.CreateModel(
            name='PartnerTarif',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nazev', models.CharField(max_length=100, unique=True, verbose_name='název')),
                ('castka', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10, verbose_name='výchozí cena')),
                ('razeni', models.PositiveSmallIntegerField(default=0, verbose_name='pořadí')),
                ('aktivni', models.BooleanField(default=True, verbose_name='aktivní')),
            ],
            options={
                'verbose_name': 'tarif',
                'verbose_name_plural': 'tarify',
                'ordering': ['razeni', 'id'],
            },
        ),
        migrations.RunPython(seed_tarify, unseed_tarify),
    ]
