from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('partner_admin', '0022_potencialni_adresni_pole'),
    ]

    operations = [
        migrations.AlterField(
            model_name='potencialnikontakt',
            name='email',
            field=models.EmailField(blank=True, null=True, unique=True, verbose_name='e-mail'),
        ),
    ]