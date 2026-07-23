from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rezervace', '0027_storno_apology_text'),
    ]

    operations = [
        migrations.AddField(
            model_name='rezervacninastaveni',
            name='imap_enabled',
            field=models.BooleanField(
                default=False,
                help_text='Zapne schránku ve FLOW (čtení / odpověď). Přihlášení = stejné jako SMTP.',
                verbose_name='IMAP pro FLOW',
            ),
        ),
        migrations.AddField(
            model_name='rezervacninastaveni',
            name='imap_host',
            field=models.CharField(
                blank=True,
                default='imap.forpsi.com',
                max_length=200,
                verbose_name='IMAP server',
            ),
        ),
        migrations.AddField(
            model_name='rezervacninastaveni',
            name='imap_port',
            field=models.PositiveIntegerField(default=993, verbose_name='IMAP port'),
        ),
        migrations.AddField(
            model_name='rezervacninastaveni',
            name='imap_use_ssl',
            field=models.BooleanField(default=True, verbose_name='IMAP SSL'),
        ),
    ]
