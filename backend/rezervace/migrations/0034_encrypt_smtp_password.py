from django.db import migrations, models


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
                help_text='Uloženo šifrovaně (enc:v1:). API heslo nikdy nevrací.',
                verbose_name='SMTP heslo',
            ),
        ),
    ]
