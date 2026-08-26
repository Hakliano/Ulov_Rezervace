from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sklad', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='recipeline',
            name='quantity',
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=12, null=True),
        ),
    ]
