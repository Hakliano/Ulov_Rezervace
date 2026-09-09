from django.db import migrations, models


def encrypt_existing_smtp_passwords(apps, schema_editor):
    from rezervace.services.smtp_secrets import encrypt_smtp_secret, is_encrypted_smtp_secret

    RezervacniNastaveni = apps.get_model('rezervace', 'RezervacniNastaveni')
    for row in RezervacniNastaveni.objects.exclude(smtp_password='').iterator():
        if is_encrypted_smtp_secret(row.smtp_password):
            continue
        row.smtp_password = encrypt_smtp_secret(row.smtp_password)
        row.save(update_fields=['smtp_password'])


def noop_reverse(apps, schema_editor):
    # Zpětná dešifrace by vrátila plaintext do DB — záměrně neděláme.
    return


class Migration(migrations.Migration):

    dependencies = [
        ('rezervace', '0033_rezervace_zaloha_nepozadovana'),
    ]

    operations = [
        migrations.AlterField(
            model_name='rezervacninastaveni',
            name='smtp_password',
            field=models.TextField(
                blank=True,
                help_text='Uloženo šifrovaně. API heslo nikdy nevrací.',
                verbose_name='SMTP heslo',
            ),
        ),
        migrations.RunPython(encrypt_existing_smtp_passwords, noop_reverse),
    ]
