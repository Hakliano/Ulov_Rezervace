from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('jadro', '0012_user02_prihlasovaci_udaje'),
    ]

    operations = [
        migrations.AddField(
            model_name='klientmodernik',
            name='mesto',
            field=models.CharField(blank=True, db_index=True, default='', max_length=120),
        ),
        migrations.AddField(
            model_name='klientmodernik',
            name='cast_obce',
            field=models.CharField(blank=True, default='', max_length=120),
        ),
        migrations.AddField(
            model_name='klientmodernik',
            name='latitude',
            field=models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name='klientmodernik',
            name='longitude',
            field=models.DecimalField(blank=True, decimal_places=7, max_digits=10, null=True),
        ),
    ]