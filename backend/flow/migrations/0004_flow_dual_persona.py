from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('flow', '0003_customer_card'),
    ]

    operations = [
        migrations.AddField(
            model_name='flowuser',
            name='pracovni_zamestnanec',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='flow_pracovni_pro',
                to='rezervace.zamestnanec',
                verbose_name='pracovní persona',
            ),
        ),
        migrations.AddField(
            model_name='flowsession',
            name='active_zamestnanec',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='flow_aktivni_sessiony',
                to='rezervace.zamestnanec',
                verbose_name='aktivní persona',
            ),
        ),
    ]
