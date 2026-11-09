from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('partner_admin', '0020_potencialni_nove_stavy'),
    ]

    operations = [
        migrations.CreateModel(
            name='PotencialniKontaktTombstone',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kontakt_id', models.PositiveIntegerField(unique=True)),
                ('smazano', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'smazaný potenciální klient (API)',
                'verbose_name_plural': 'smazaní potenciální klienti (API)',
            },
        ),
        migrations.CreateModel(
            name='PotencialniKontaktStavHistorie',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('stav_pred', models.CharField(blank=True, default='', max_length=32)),
                ('stav', models.CharField(max_length=32)),
                ('zmenil', models.CharField(blank=True, default='', max_length=120)),
                ('vytvoreno', models.DateTimeField(auto_now_add=True)),
                ('kontakt', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='stav_historie', to='partner_admin.potencialnikontakt')),
            ],
            options={
                'verbose_name': 'historie stavu potenciálního klienta',
                'verbose_name_plural': 'historie stavů potenciálních klientů',
                'ordering': ['-vytvoreno'],
            },
        ),
    ]
