from django.db import migrations, models


def add_ulov_ucet_and_faktura(apps, schema_editor):
    connection = schema_editor.connection
    vendor = connection.vendor
    if vendor == 'postgresql':
        schema_editor.execute(
            """
            ALTER TABLE partner_admin_partnernastaveni
              ADD COLUMN IF NOT EXISTS ulov_cislo_uctu varchar(34) DEFAULT '' NOT NULL;
            ALTER TABLE partner_admin_platbapartnera
              ADD COLUMN IF NOT EXISTS faktura_pdf varchar(100) NULL;
            """
        )
        return
    with connection.cursor() as cursor:
        cursor.execute('PRAGMA table_info(partner_admin_partnernastaveni)')
        nast_cols = {row[1] for row in cursor.fetchall()}
        if 'ulov_cislo_uctu' not in nast_cols:
            cursor.execute(
                "ALTER TABLE partner_admin_partnernastaveni "
                "ADD COLUMN ulov_cislo_uctu varchar(34) DEFAULT '' NOT NULL"
            )
        cursor.execute('PRAGMA table_info(partner_admin_platbapartnera)')
        platba_cols = {row[1] for row in cursor.fetchall()}
        if 'faktura_pdf' not in platba_cols:
            cursor.execute(
                "ALTER TABLE partner_admin_platbapartnera "
                "ADD COLUMN faktura_pdf varchar(100) NULL"
            )


class Migration(migrations.Migration):

    dependencies = [
        ('partner_admin', '0004_upozorneniplatby_text'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='partnernastaveni',
                    name='ulov_cislo_uctu',
                    field=models.CharField(
                        blank=True,
                        help_text='Číslo účtu ULOV ve formátu číslo/kód banky nebo IBAN. Není to účet personálu.',
                        max_length=34,
                        verbose_name='účet ULOV (pro QR / převod)',
                    ),
                ),
                migrations.AddField(
                    model_name='platbapartnera',
                    name='faktura_pdf',
                    field=models.FileField(
                        blank=True,
                        null=True,
                        upload_to='partner_faktury/%Y/%m/',
                        verbose_name='faktura PDF',
                    ),
                ),
            ],
            database_operations=[
                migrations.RunPython(add_ulov_ucet_and_faktura, migrations.RunPython.noop),
            ],
        ),
    ]
