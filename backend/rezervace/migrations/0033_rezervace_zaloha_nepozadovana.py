from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rezervace', '0032_unique_owner_login_email'),
    ]

    operations = [
        migrations.AddField(
            model_name='rezervace',
            name='zaloha_nepozadovana_at',
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name='záloha nepožadována (důvěryhodný host)',
            ),
        ),
    ]
