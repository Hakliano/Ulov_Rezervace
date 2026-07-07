from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('salons', '0001_initial'),
        ('rezervace', '0008_rezervacninastaveni_recenze_url'),
    ]

    operations = [
        migrations.CreateModel(
            name='NoShowZaznam',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('jmeno', models.CharField(max_length=100, verbose_name='jméno')),
                ('email', models.EmailField(max_length=254, verbose_name='e-mail')),
                ('zacatek', models.DateTimeField(verbose_name='termín rezervace')),
                ('zamestnanec_jmeno', models.CharField(blank=True, max_length=100, verbose_name='pracovník')),
                ('sluzby', models.CharField(blank=True, max_length=500, verbose_name='služby')),
                ('email_upozorneni_odeslan', models.BooleanField(default=False, verbose_name='upozornění odesláno')),
                ('zakaznik_blokovan', models.BooleanField(default=False, verbose_name='zákazník zablokován')),
                ('vytvoreno', models.DateTimeField(auto_now_add=True)),
                ('rezervace', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='no_show_zaznam', to='rezervace.rezervace')),
                ('salon', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='no_show_zaznamy', to='salons.salon')),
                ('zakaznik', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='no_show_zaznamy', to='rezervace.zakaznik')),
            ],
            options={
                'verbose_name': 'no-show záznam',
                'verbose_name_plural': 'no-show archiv',
                'ordering': ['-vytvoreno'],
            },
        ),
    ]
