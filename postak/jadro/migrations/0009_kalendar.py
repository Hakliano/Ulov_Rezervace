from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('jadro', '0008_klienti_hya'),
    ]

    operations = [
        migrations.CreateModel(
            name='KalendarUdalost',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nazev', models.CharField(max_length=200)),
                ('zacatek', models.DateTimeField(db_index=True)),
                ('konec', models.DateTimeField()),
                ('typ', models.CharField(choices=[('schuzka', 'Schůzka'), ('telefonat', 'Telefonát'), ('ukol', 'Úkol'), ('ostatni', 'Ostatní')], db_index=True, max_length=16)),
                ('popis', models.TextField(blank=True, default='')),
                ('hotovo', models.BooleanField(default=False)),
                ('vytvoreno', models.DateTimeField(auto_now_add=True)),
                ('upraveno', models.DateTimeField(auto_now=True)),
                ('klient_hya', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='kalendar_udalosti', to='jadro.klienthya')),
                ('klient_modernik', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='kalendar_udalosti', to='jadro.klientmodernik')),
                ('prirazeny', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='kalendar_udalosti', to=settings.AUTH_USER_MODEL)),
                ('vytvoril', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='kalendar_vytvorene', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['zacatek', 'id'],
            },
        ),
        migrations.AddIndex(
            model_name='kalendarudalost',
            index=models.Index(fields=['prirazeny', 'zacatek'], name='kal_pri_zac_idx'),
        ),
        migrations.AddIndex(
            model_name='kalendarudalost',
            index=models.Index(fields=['typ', 'hotovo'], name='kal_typ_hot_idx'),
        ),
    ]
