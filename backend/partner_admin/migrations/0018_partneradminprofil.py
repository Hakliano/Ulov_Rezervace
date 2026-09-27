from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('partner_admin', '0017_potencialni_klienti'),
    ]

    operations = [
        migrations.CreateModel(
            name='PartnerAdminProfil',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('jmeno', models.CharField(max_length=150, verbose_name='jméno')),
                ('role', models.CharField(
                    choices=[('kam', 'KAM'), ('admin_finance', 'ADMIN/Finance')],
                    max_length=32,
                    verbose_name='role',
                )),
                ('vytvoreno', models.DateTimeField(auto_now_add=True)),
                ('user', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='partner_admin_profil',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'profil partner-admin',
                'verbose_name_plural': 'profily partner-admin',
                'ordering': ['jmeno'],
            },
        ),
    ]
