from django.db import migrations, models
import django.db.models.deletion


def oznac_existujici_jako_testovaci(apps, schema_editor):
    PartnerNastaveni = apps.get_model('partner_admin', 'PartnerNastaveni')
    PartnerNastaveni.objects.update(je_testovaci=True)


def seed_ulov_ucty(apps, schema_editor):
    PartnerNastaveni = apps.get_model('partner_admin', 'PartnerNastaveni')
    UlovCisloUctu = apps.get_model('partner_admin', 'UlovCisloUctu')
    seen = []
    for cislo in (
        PartnerNastaveni.objects.exclude(ulov_cislo_uctu='')
        .values_list('ulov_cislo_uctu', flat=True)
        .distinct()
    ):
        hodnota = (cislo or '').strip()
        if not hodnota or hodnota in seen:
            continue
        seen.append(hodnota)
        UlovCisloUctu.objects.create(
            cislo=hodnota,
            primarni=len(seen) == 1,
            aktivni=True,
            razeni=len(seen) * 10,
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('partner_admin', '0009_prehled_emaily_chyby'),
    ]

    operations = [
        migrations.CreateModel(
            name='KeyAccountManager',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('jmeno', models.CharField(max_length=120, unique=True, verbose_name='jméno')),
                ('email', models.EmailField(blank=True, max_length=254, verbose_name='e-mail')),
                ('telefon', models.CharField(blank=True, max_length=50, verbose_name='telefon')),
                ('aktivni', models.BooleanField(default=True, verbose_name='aktivní')),
                ('razeni', models.PositiveSmallIntegerField(default=0, verbose_name='pořadí')),
            ],
            options={
                'verbose_name': 'KAM',
                'verbose_name_plural': 'KAM',
                'ordering': ['razeni', 'jmeno'],
            },
        ),
        migrations.CreateModel(
            name='UlovCisloUctu',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cislo', models.CharField(max_length=34, unique=True, verbose_name='číslo účtu')),
                ('popisek', models.CharField(blank=True, max_length=80, verbose_name='kam / poznámka')),
                ('primarni', models.BooleanField(default=False, verbose_name='primární (QR)')),
                ('aktivni', models.BooleanField(default=True, verbose_name='aktivní')),
                ('razeni', models.PositiveSmallIntegerField(default=0, verbose_name='pořadí')),
            ],
            options={
                'verbose_name': 'číslo účtu ULOV',
                'verbose_name_plural': 'čísla účtů ULOV',
                'ordering': ['-primarni', 'razeni', 'id'],
            },
        ),
        migrations.AddField(
            model_name='partnernastaveni',
            name='je_testovaci',
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text='Jen interní dema. Noví zákazníci sem nepatří. Viditelné v Testovacích přístupech.',
                verbose_name='testovací partner',
            ),
        ),
        migrations.AddField(
            model_name='partnernastaveni',
            name='kam',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='partneri',
                to='partner_admin.keyaccountmanager',
                verbose_name='KAM',
            ),
        ),
        migrations.RunPython(oznac_existujici_jako_testovaci, noop_reverse),
        migrations.RunPython(seed_ulov_ucty, noop_reverse),
    ]
