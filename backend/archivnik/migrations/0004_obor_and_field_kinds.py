import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('archivnik', '0003_object_cover'),
        ('salons', '0008_cenikpolozka_rizikovy'),
    ]

    operations = [
        migrations.CreateModel(
            name='Obor',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('uuid', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('nazev', models.CharField(max_length=80, verbose_name='název')),
                ('poradi', models.PositiveSmallIntegerField(default=0)),
                ('zdroj_preset', models.CharField(blank=True, default='', help_text='Kód presetu v okamžiku kopie. Nikdy se z katalogu znovu nesynchronizuje.', max_length=32)),
                ('vytvoreno', models.DateTimeField(auto_now_add=True)),
                ('upraveno', models.DateTimeField(auto_now=True)),
                ('salon', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='archivnik_obory', to='salons.salon')),
            ],
            options={
                'verbose_name': 'obor',
                'verbose_name_plural': 'obory',
                'ordering': ['poradi', 'nazev'],
            },
        ),
        migrations.AddField(
            model_name='objecttype',
            name='obor',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='typy', to='archivnik.obor'),
        ),
        migrations.AddField(
            model_name='customfielddef',
            name='volby',
            field=models.JSONField(blank=True, default=list, verbose_name='možnosti výběru'),
        ),
        migrations.AlterField(
            model_name='customfielddef',
            name='druh',
            field=models.CharField(choices=[('text', 'Text'), ('dlouhy_text', 'Dlouhý text'), ('cislo', 'Číslo'), ('datum', 'Datum'), ('ano_ne', 'Ano / ne'), ('vyber', 'Výběr')], default='text', max_length=16),
        ),
        migrations.AlterField(
            model_name='customfieldvalue',
            name='hodnota',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddConstraint(
            model_name='obor',
            constraint=models.UniqueConstraint(fields=('salon', 'nazev'), name='archivnik_obor_salon_nazev'),
        ),
        migrations.AddConstraint(
            model_name='obor',
            constraint=models.UniqueConstraint(condition=models.Q(('zdroj_preset', ''), _negated=True), fields=('salon', 'zdroj_preset'), name='archivnik_obor_salon_preset'),
        ),
    ]
