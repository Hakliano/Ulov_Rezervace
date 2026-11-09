from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('jadro', '0005_email_koncept'),
    ]

    operations = [
        migrations.CreateModel(
            name='KlientSektor',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('remote_id', models.PositiveIntegerField(unique=True)),
                ('nazev', models.CharField(max_length=80)),
                ('razeni', models.PositiveSmallIntegerField(default=100)),
            ],
            options={'ordering': ['razeni', 'nazev']},
        ),
        migrations.CreateModel(
            name='KlientSyncMeta',
            fields=[
                ('id', models.PositiveSmallIntegerField(default=1, editable=False, primary_key=True, serialize=False)),
                ('posledni_delta', models.DateTimeField(blank=True, null=True)),
                ('posledni_nocni', models.DateTimeField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='KlientModernik',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('remote_id', models.PositiveIntegerField(db_index=True, unique=True)),
                ('jmeno', models.CharField(db_index=True, max_length=200)),
                ('email', models.EmailField(db_index=True, max_length=254)),
                ('telefon', models.CharField(blank=True, default='', max_length=200)),
                ('web', models.CharField(blank=True, default='', max_length=400)),
                ('adresa', models.TextField(blank=True, default='')),
                ('ico', models.CharField(blank=True, default='', max_length=20)),
                ('poznamka', models.TextField(blank=True, default='')),
                ('stav', models.CharField(db_index=True, max_length=32)),
                ('stav_label', models.CharField(blank=True, default='', max_length=80)),
                ('sektor_remote_id', models.PositiveIntegerField(blank=True, null=True)),
                ('sektor_nazev', models.CharField(blank=True, default='', max_length=80)),
                ('remote_upraveno', models.DateTimeField()),
                ('cached', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'klient Moderník (cache)',
                'verbose_name_plural': 'klienti Moderník (cache)',
                'ordering': ['-remote_upraveno'],
            },
        ),
        migrations.CreateModel(
            name='KlientStavHistorie',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('stav', models.CharField(max_length=32)),
                ('stav_pred', models.CharField(blank=True, default='', max_length=32)),
                ('stav_label', models.CharField(blank=True, default='', max_length=80)),
                ('kdo', models.CharField(blank=True, default='', max_length=120)),
                ('kdy', models.DateTimeField()),
                ('klient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='stav_historie', to='jadro.klientmodernik')),
            ],
            options={'ordering': ['-kdy']},
        ),
    ]
