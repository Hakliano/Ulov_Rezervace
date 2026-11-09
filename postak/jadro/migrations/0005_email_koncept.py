from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import jadro.models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('jadro', '0004_poznamka_koncept'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmailKoncept',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('komu', models.TextField(blank=True, default='', verbose_name='komu')),
                ('kopie', models.TextField(blank=True, default='', verbose_name='kopie')),
                ('skryte', models.TextField(blank=True, default='', verbose_name='skrytá kopie')),
                ('predmet', models.CharField(blank=True, default='', max_length=500, verbose_name='předmět')),
                ('telo_html', models.TextField(blank=True, default='', verbose_name='tělo (HTML)')),
                ('in_reply_to', models.CharField(blank=True, default='', max_length=300)),
                ('vytvoreno', models.DateTimeField(auto_now_add=True)),
                ('upraveno', models.DateTimeField(auto_now=True)),
                ('schranka', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='koncepty', to='jadro.emailschranka')),
                ('vlastnik', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='email_koncepty', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'koncept e-mailu',
                'verbose_name_plural': 'koncepty e-mailů',
                'ordering': ['-upraveno'],
            },
        ),
        migrations.CreateModel(
            name='EmailKonceptPriloha',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('soubor', models.FileField(upload_to=jadro.models._koncept_upload)),
                ('nazev', models.CharField(max_length=255)),
                ('content_type', models.CharField(default='application/octet-stream', max_length=120)),
                ('velikost', models.PositiveIntegerField(default=0)),
                ('vytvoreno', models.DateTimeField(auto_now_add=True)),
                ('koncept', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='prilohy', to='jadro.emailkoncept')),
            ],
            options={
                'verbose_name': 'příloha konceptu',
                'verbose_name_plural': 'přílohy konceptu',
            },
        ),
    ]
