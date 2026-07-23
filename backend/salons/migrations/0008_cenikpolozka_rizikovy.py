from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('salons', '0007_salon_banner'),
    ]

    operations = [
        migrations.AddField(
            model_name='cenikpolozka',
            name='rizikovy',
            field=models.BooleanField(
                default=False,
                help_text='Upozorní personál ve FLOW; do potvrzení se doplní text o možné záloze.',
                verbose_name='rizikový produkt (možná záloha)',
            ),
        ),
    ]
