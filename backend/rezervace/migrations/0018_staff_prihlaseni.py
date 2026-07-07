from django.db import migrations, models
import uuid

from django.contrib.auth.hashers import make_password


def vytvor_prihlaseni(apps, schema_editor):
    Zamestnanec = apps.get_model('rezervace', 'Zamestnanec')
    Salon = apps.get_model('salons', 'Salon')

    for salon in Salon.objects.all():
        majitel, created = Zamestnanec.objects.get_or_create(
            salon=salon,
            role='majitel',
            defaults={
                'jmeno': 'Majitelka',
                'prihlasovaci_jmeno': 'majitelka',
                'password_hash': make_password('majitelka123'),
                'zobrazit_na_webu': False,
                'aktivni': True,
                'poradi': 999,
            },
        )
        if not created and not majitel.prihlasovaci_jmeno:
            majitel.prihlasovaci_jmeno = 'majitelka'
            majitel.password_hash = make_password('majitelka123')
            majitel.save(update_fields=['prihlasovaci_jmeno', 'password_hash'])

        for z in Zamestnanec.objects.filter(salon=salon).exclude(role='majitel'):
            if z.prihlasovaci_jmeno:
                continue
            login = z.jmeno.strip().lower()
            login = {
                'petra': 'petra', 'jana': 'jana', 'lenka': 'lenka',
                'markéta': 'marketa', 'marketa': 'marketa', 'eva': 'eva',
            }.get(login, login.replace(' ', ''))
            if Zamestnanec.objects.filter(salon=salon, prihlasovaci_jmeno=login).exists():
                login = f'{login}{z.id}'
            z.prihlasovaci_jmeno = login
            z.password_hash = make_password(f'{login}123')
            z.role = 'zamestnanec'
            z.save(update_fields=['prihlasovaci_jmeno', 'password_hash', 'role'])


class Migration(migrations.Migration):

    dependencies = [
        ('rezervace', '0017_zivotni_cyklus_stavy'),
    ]

    operations = [
        migrations.AddField(
            model_name='zamestnanec',
            name='password_hash',
            field=models.CharField(blank=True, max_length=128, verbose_name='heslo (hash)'),
        ),
        migrations.AddField(
            model_name='zamestnanec',
            name='prihlasovaci_jmeno',
            field=models.CharField(blank=True, max_length=50, verbose_name='přihlašovací jméno'),
        ),
        migrations.AddField(
            model_name='zamestnanec',
            name='role',
            field=models.CharField(
                choices=[('majitel', 'Majitel / majitelka'), ('zamestnanec', 'Zaměstnanec')],
                default='zamestnanec',
                max_length=20,
                verbose_name='role',
            ),
        ),
        migrations.RunPython(vytvor_prihlaseni, migrations.RunPython.noop),
        migrations.AlterUniqueTogether(
            name='zamestnanec',
            unique_together={('salon', 'prihlasovaci_jmeno')},
        ),
        migrations.CreateModel(
            name='ZamestnanecSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('vytvoreno', models.DateTimeField(auto_now_add=True)),
                ('expirace', models.DateTimeField()),
                ('zamestnanec', models.ForeignKey(
                    on_delete=models.deletion.CASCADE,
                    related_name='sessiony',
                    to='rezervace.zamestnanec',
                )),
            ],
            options={
                'verbose_name': 'session zaměstnance',
                'verbose_name_plural': 'sessiony zaměstnanců',
            },
        ),
    ]