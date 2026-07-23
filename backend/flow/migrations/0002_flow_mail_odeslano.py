from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('flow', '0001_initial_flow_user'),
    ]

    operations = [
        migrations.CreateModel(
            name='FlowMailOdeslano',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('prijemce', models.EmailField(max_length=254, verbose_name='příjemce')),
                ('predmet', models.CharField(max_length=300, verbose_name='předmět')),
                ('telo', models.TextField(verbose_name='text')),
                ('vytvoreno', models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    'odeslal',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='odeslane_maily',
                        to='flow.flowuser',
                    ),
                ),
                (
                    'salon',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='flow_mail_odeslane',
                        to='salons.salon',
                    ),
                ),
            ],
            options={
                'verbose_name': 'FLOW odeslaný e-mail',
                'verbose_name_plural': 'FLOW odeslané e-maily',
                'ordering': ['-vytvoreno'],
            },
        ),
    ]
