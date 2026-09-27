from django.db import migrations, models
import django.db.models.deletion


def seed_sektory(apps, schema_editor):
    PotencialniSektor = apps.get_model('partner_admin', 'PotencialniSektor')
    for nazev, razeni in (
        ('Beauty', 10),
        ('Veterina', 20),
        ('Servis', 30),
        ('nezařazeno', 90),
    ):
        PotencialniSektor.objects.get_or_create(nazev=nazev, defaults={'razeni': razeni})


def unseed_sektory(apps, schema_editor):
    PotencialniSektor = apps.get_model('partner_admin', 'PotencialniSektor')
    PotencialniSektor.objects.filter(nazev__in=['Beauty', 'Veterina', 'Servis', 'nezařazeno']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('partner_admin', '0016_tarify_archivnik'),
    ]

    operations = [
        migrations.CreateModel(
            name='PotencialniSektor',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nazev', models.CharField(max_length=80, unique=True, verbose_name='název')),
                ('razeni', models.PositiveSmallIntegerField(default=100, verbose_name='pořadí')),
                ('vytvoreno', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'sektor potenciálního klienta',
                'verbose_name_plural': 'sektory potenciálních klientů',
                'ordering': ['razeni', 'nazev'],
            },
        ),
        migrations.CreateModel(
            name='PotencialniKontakt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('jmeno', models.CharField(db_index=True, max_length=200, verbose_name='jméno')),
                ('email', models.EmailField(max_length=254, unique=True, verbose_name='e-mail')),
                ('telefon', models.CharField(blank=True, default='', max_length=200, verbose_name='telefon')),
                ('web', models.CharField(blank=True, default='', max_length=400, verbose_name='web')),
                ('adresa', models.TextField(blank=True, default='', verbose_name='adresa')),
                ('ico', models.CharField(blank=True, default='', max_length=20, verbose_name='IČO')),
                ('poznamka', models.TextField(blank=True, default='', verbose_name='poznámka')),
                ('stav', models.CharField(
                    choices=[
                        ('lead_pred_webu', 'Lead před kontrolou webu'),
                        ('lead_po_webu', 'Lead po kontrole webu'),
                        ('kontakt_email', 'Kontaktován e-mailem'),
                        ('kontakt_sms', 'Kontaktován SMS'),
                        ('kontakt_telefon', 'Kontaktován telefonicky'),
                        ('kontakt_osobne', 'Kontaktován osobně'),
                        ('nema_zajem', 'Nemá zájem'),
                        ('ma_zajem', 'Má zájem'),
                        ('nechceme', 'Nechceme'),
                    ],
                    db_index=True,
                    default='lead_pred_webu',
                    max_length=32,
                    verbose_name='stav',
                )),
                ('vytvoreno', models.DateTimeField(auto_now_add=True)),
                ('upraveno', models.DateTimeField(auto_now=True)),
                ('sektor', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='kontakty',
                    to='partner_admin.potencialnisektor',
                )),
            ],
            options={
                'verbose_name': 'potenciální klient',
                'verbose_name_plural': 'potenciální klienti',
                'ordering': ['-id'],
            },
        ),
        migrations.AddIndex(
            model_name='potencialnikontakt',
            index=models.Index(fields=['stav', 'jmeno'], name='potkontakt_stav_jmeno_idx'),
        ),
        migrations.RunPython(seed_sektory, unseed_sektory),
    ]
