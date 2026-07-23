from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rezervace', '0028_imap_flow_mail'),
    ]

    operations = [
        migrations.AddField(
            model_name='rezervace',
            name='zaloha_castka',
            field=models.DecimalField(
                blank=True, decimal_places=0, max_digits=10, null=True,
                verbose_name='částka zálohy (Kč)',
            ),
        ),
        migrations.AddField(
            model_name='rezervace',
            name='zaloha_ok_at',
            field=models.DateTimeField(
                blank=True, null=True, verbose_name='záloha potvrzena personálem',
            ),
        ),
        migrations.AddField(
            model_name='rezervace',
            name='zaloha_vyzadana_at',
            field=models.DateTimeField(
                blank=True, null=True, verbose_name='žádost o zálohu odeslána',
            ),
        ),
    ]
