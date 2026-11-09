from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('jadro', '0006_klienti_modernik'),
    ]

    operations = [
        migrations.AddField(
            model_name='profil',
            name='telefon',
            field=models.CharField(blank=True, default='', max_length=40, verbose_name='telefon'),
        ),
        migrations.CreateModel(
            name='ChatZprava',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text', models.TextField(max_length=5000)),
                ('precteno', models.BooleanField(default=False)),
                ('vytvoreno', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('odesilatel', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='chat_odeslane', to=settings.AUTH_USER_MODEL)),
                ('prijemce', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='chat_prijate', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['vytvoreno'],
            },
        ),
        migrations.AddIndex(
            model_name='chatzprava',
            index=models.Index(fields=['prijemce', 'precteno'], name='chat_prij_prect_idx'),
        ),
        migrations.AddIndex(
            model_name='chatzprava',
            index=models.Index(fields=['odesilatel', 'prijemce'], name='chat_pair_idx'),
        ),
    ]
