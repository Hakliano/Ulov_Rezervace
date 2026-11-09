from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('jadro', '0003_podpis_html'),
    ]

    operations = [
        migrations.CreateModel(
            name='PoznamkaKoncept',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nazev', models.CharField(max_length=200, verbose_name='název')),
                ('poradi', models.IntegerField(default=0, verbose_name='pořadí')),
                ('obsah_html', models.TextField(blank=True, default='', verbose_name='obsah (HTML)')),
                ('vytvoreno', models.DateTimeField(auto_now_add=True)),
                ('upraveno', models.DateTimeField(auto_now=True)),
                ('vlastnik', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='poznamky_koncepty', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'poznámka / koncept',
                'verbose_name_plural': 'poznámky a koncepty',
                'ordering': ['poradi', '-upraveno'],
            },
        ),
    ]
