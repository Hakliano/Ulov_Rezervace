from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('jadro', '0013_klient_modernik_adresa'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='profil',
            name='posledni_aktivita',
            field=models.DateTimeField(blank=True, db_index=True, null=True, verbose_name='poslední aktivita'),
        ),
        migrations.CreateModel(
            name='PrihlaseniHistorie',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('vytvoreno', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('uzivatel', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='prihlaseni_historie', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'historie přihlášení',
                'verbose_name_plural': 'historie přihlášení',
                'ordering': ['-vytvoreno'],
            },
        ),
    ]