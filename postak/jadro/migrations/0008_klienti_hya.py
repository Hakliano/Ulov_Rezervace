from django.db import migrations, models


def ensure_sync_rows(apps, schema_editor):
    KlientSyncMeta = apps.get_model('jadro', 'KlientSyncMeta')
    KlientSyncMeta.objects.get_or_create(pk=1)
    KlientSyncMeta.objects.get_or_create(pk=2)


class Migration(migrations.Migration):

    dependencies = [
        ('jadro', '0007_profil_telefon_chat'),
    ]

    operations = [
        migrations.AddField(
            model_name='klientsyncmeta',
            name='posledni_chyba',
            field=models.CharField(blank=True, default='', max_length=300),
        ),
        migrations.CreateModel(
            name='KlientHya',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('remote_id', models.PositiveIntegerField(db_index=True, unique=True)),
                ('jmeno', models.CharField(db_index=True, max_length=200)),
                ('kontakt_jmeno', models.CharField(blank=True, default='', max_length=200)),
                ('email', models.EmailField(blank=True, db_index=True, default='', max_length=254)),
                ('telefon', models.CharField(blank=True, default='', max_length=200)),
                ('web', models.CharField(blank=True, default='', max_length=400)),
                ('lokalita', models.CharField(blank=True, default='', max_length=200)),
                ('zdroj', models.CharField(blank=True, default='', max_length=120)),
                ('ma_web', models.CharField(blank=True, default='', max_length=12)),
                ('ma_rezervace', models.CharField(blank=True, default='', max_length=12)),
                ('poznamka', models.TextField(blank=True, default='')),
                ('stav', models.CharField(db_index=True, max_length=32)),
                ('stav_label', models.CharField(blank=True, default='', max_length=80)),
                ('remote_upraveno', models.DateTimeField()),
                ('cached', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'klient HereYouAre (cache)',
                'verbose_name_plural': 'klienti HereYouAre (cache)',
                'ordering': ['-remote_upraveno'],
            },
        ),
        migrations.RunPython(ensure_sync_rows, migrations.RunPython.noop),
    ]
