import uuid

from django.db import migrations, models
import django.db.models.deletion


def seed_katalog(apps, schema_editor):
    ModulKatalog = apps.get_model('partner_admin', 'ModulKatalog')
    ModulKatalog.objects.get_or_create(
        kod='materialnik',
        defaults={
            'nazev': 'Materiálník',
            'popis': 'Sklad materiálů, receptury a spotřeba. Funguje i bez FLOW.',
            'razeni': 10,
        },
    )


def unseed_katalog(apps, schema_editor):
    ModulKatalog = apps.get_model('partner_admin', 'ModulKatalog')
    ModulKatalog.objects.filter(kod='materialnik').delete()


def fill_tenant_uuid(apps, schema_editor):
    PartnerNastaveni = apps.get_model('partner_admin', 'PartnerNastaveni')
    for row in PartnerNastaveni.objects.all():
        if not row.tenant_uuid:
            row.tenant_uuid = uuid.uuid4()
            row.save(update_fields=['tenant_uuid'])


def make_tenant_uuid_unique(apps, schema_editor):
    table = 'partner_admin_partnernastaveni'
    vendor = schema_editor.connection.vendor
    if vendor == 'postgresql':
        schema_editor.execute(
            f'ALTER TABLE {table} ALTER COLUMN tenant_uuid SET NOT NULL'
        )
        schema_editor.execute(
            f'CREATE UNIQUE INDEX IF NOT EXISTS partner_admin_tenant_uuid_uniq '
            f'ON {table} (tenant_uuid)'
        )
    else:
        schema_editor.execute(
            f'CREATE UNIQUE INDEX partner_admin_tenant_uuid_uniq ON {table} (tenant_uuid)'
        )


def drop_tenant_uuid_unique(apps, schema_editor):
    table = 'partner_admin_partnernastaveni'
    vendor = schema_editor.connection.vendor
    schema_editor.execute('DROP INDEX IF EXISTS partner_admin_tenant_uuid_uniq')
    if vendor == 'postgresql':
        schema_editor.execute(
            f'ALTER TABLE {table} ALTER COLUMN tenant_uuid DROP NOT NULL'
        )


def add_tenant_uuid_column(apps, schema_editor):
    table = 'partner_admin_partnernastaveni'
    connection = schema_editor.connection
    if connection.vendor == 'postgresql':
        schema_editor.execute(
            f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS tenant_uuid uuid NULL'
        )
        return
    with connection.cursor() as cursor:
        cursor.execute(f'PRAGMA table_info({table})')
        cols = {row[1] for row in cursor.fetchall()}
        if 'tenant_uuid' not in cols:
            cursor.execute(f'ALTER TABLE {table} ADD COLUMN tenant_uuid char(32) NULL')


class Migration(migrations.Migration):

    dependencies = [
        ('partner_admin', '0006_povolit_technicke_nastaveni'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(add_tenant_uuid_column, migrations.RunPython.noop),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='partnernastaveni',
                    name='tenant_uuid',
                    field=models.UUIDField(null=True, editable=False, verbose_name='veřejné ID tenanta'),
                ),
            ],
        ),
        migrations.RunPython(fill_tenant_uuid, migrations.RunPython.noop),
        migrations.RunPython(make_tenant_uuid_unique, drop_tenant_uuid_unique),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name='partnernastaveni',
                    name='tenant_uuid',
                    field=models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        unique=True,
                        verbose_name='veřejné ID tenanta',
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name='ModulKatalog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kod', models.SlugField(max_length=40, unique=True, verbose_name='kód')),
                ('nazev', models.CharField(max_length=80, verbose_name='název')),
                ('popis', models.CharField(blank=True, max_length=300, verbose_name='popis')),
                ('razeni', models.PositiveSmallIntegerField(default=0, verbose_name='pořadí')),
            ],
            options={
                'verbose_name': 'modul v katalogu',
                'verbose_name_plural': 'katalog modulů',
                'ordering': ['razeni', 'kod'],
            },
        ),
        migrations.CreateModel(
            name='PartnerModul',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'Zapíná se'),
                        ('active', 'Aktivní'),
                        ('inactive', 'Vypnuto'),
                        ('error', 'Chyba'),
                    ],
                    db_index=True,
                    default='inactive',
                    max_length=20,
                )),
                ('hmac_key', models.CharField(blank=True, max_length=128)),
                ('provisioning_error', models.TextField(blank=True, verbose_name='chyba provisioningu')),
                ('activated_at', models.DateTimeField(blank=True, null=True)),
                ('deactivated_at', models.DateTimeField(blank=True, null=True)),
                ('aktualizovano', models.DateTimeField(auto_now=True)),
                ('modul', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='partneri',
                    to='partner_admin.modulkatalog',
                )),
                ('salon', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='moduly',
                    to='salons.salon',
                )),
            ],
            options={
                'verbose_name': 'modul partnera',
                'verbose_name_plural': 'moduly partnerů',
                'unique_together': {('salon', 'modul')},
            },
        ),
        migrations.CreateModel(
            name='IntegrationOutbox',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_id', models.CharField(max_length=64, unique=True)),
                ('event_type', models.CharField(max_length=80)),
                ('payload', models.JSONField(default=dict)),
                ('status', models.CharField(
                    choices=[
                        ('pending', 'Čeká'),
                        ('sent', 'Odesláno'),
                        ('failed', 'Chyba'),
                        ('skipped', 'Přeskočeno'),
                    ],
                    db_index=True,
                    default='pending',
                    max_length=20,
                )),
                ('attempts', models.PositiveSmallIntegerField(default=0)),
                ('last_error', models.CharField(blank=True, max_length=400)),
                ('next_attempt_at', models.DateTimeField(blank=True, db_index=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('sent_at', models.DateTimeField(blank=True, null=True)),
                ('salon', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='integration_outbox',
                    to='salons.salon',
                )),
            ],
            options={
                'verbose_name': 'integration outbox',
                'verbose_name_plural': 'integration outbox',
                'ordering': ['created_at'],
            },
        ),
        migrations.RunPython(seed_katalog, unseed_katalog),
    ]
