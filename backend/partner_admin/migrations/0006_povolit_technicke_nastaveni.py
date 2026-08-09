from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('partner_admin', '0005_ulov_ucet_faktura_pdf'),
    ]

    operations = [
        migrations.AddField(
            model_name='partnernastaveni',
            name='povolit_technicke_nastaveni',
            field=models.BooleanField(
                default=False,
                help_text=(
                    'Když je zapnuto, majitel ve FLOW Správě vidí zónu Technické nastavení '
                    '(rezervační pravidla, e-mailové šablony, audit log).'
                ),
                verbose_name='povolit Technické nastavení ve FLOW',
            ),
        ),
    ]
