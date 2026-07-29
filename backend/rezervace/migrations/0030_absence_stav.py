from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('rezervace', '0029_rezervace_zaloha'),
    ]

    operations = [
        migrations.AddField(
            model_name='zamestnanecabsence',
            name='stav',
            field=models.CharField(
                choices=[
                    ('ceka', 'Čeká na schválení'),
                    ('schvaleno', 'Schváleno'),
                    ('zamitnuto', 'Zamítnuto'),
                ],
                db_index=True,
                default='schvaleno',
                max_length=20,
                verbose_name='stav',
            ),
        ),
        migrations.AddField(
            model_name='zamestnanecabsence',
            name='vytvoreno',
            field=models.DateTimeField(
                auto_now_add=True,
                default=django.utils.timezone.now,
                verbose_name='vytvořeno',
            ),
            preserve_default=False,
        ),
    ]
