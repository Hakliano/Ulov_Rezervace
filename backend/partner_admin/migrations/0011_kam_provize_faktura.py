from decimal import Decimal

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('partner_admin', '0010_kam_test_ucty'),
        ('salons', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='keyaccountmanager',
            name='cislo_uctu',
            field=models.CharField(blank=True, max_length=34, verbose_name='číslo účtu'),
        ),
        migrations.AddField(
            model_name='partnernastaveni',
            name='prvni_platba',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('0.00'),
                help_text='Instalační balíček nebo první tarif. V tom měsíci se už nenačítá další 499/598.',
                max_digits=10,
                verbose_name='první platba',
            ),
        ),
        migrations.AddField(
            model_name='partnernastaveni',
            name='kam_provize',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('0.00'),
                help_text='Kolik dostane KAM po zaplacení první platby. 0 = nepočítat.',
                max_digits=10,
                verbose_name='provize KAM',
            ),
        ),
        migrations.AddField(
            model_name='partnernastaveni',
            name='kam_procento',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('0.00'),
                help_text='Volitelné. Z přijatých plateb po první platbě.',
                max_digits=5,
                verbose_name='provize KAM z dalších plateb (%)',
            ),
        ),
        migrations.AddField(
            model_name='partnernastaveni',
            name='ico',
            field=models.CharField(blank=True, max_length=12, verbose_name='IČO odběratele'),
        ),
        migrations.AddField(
            model_name='platbapartnera',
            name='cislo_faktury',
            field=models.CharField(blank=True, max_length=30, verbose_name='číslo faktury'),
        ),
        migrations.CreateModel(
            name='KamProvize',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('typ', models.CharField(choices=[('prvni', 'První platba'), ('procento', 'Procento z přijatého')], default='prvni', max_length=20)),
                ('obdobi', models.DateField(db_index=True, verbose_name='období (1. den měsíce)')),
                ('castka', models.DecimalField(decimal_places=2, max_digits=10)),
                ('prvni_platba', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10)),
                ('stav', models.CharField(choices=[('k_vyplate', 'K výplatě'), ('vyplaceno', 'Vyplaceno')], db_index=True, default='k_vyplate', max_length=20)),
                ('uvolneno_dne', models.DateField()),
                ('vyplaceno_dne', models.DateField(blank=True, null=True)),
                ('poznamka', models.CharField(blank=True, max_length=300)),
                ('kam', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='provize', to='partner_admin.keyaccountmanager')),
                ('platba', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='kam_provize', to='partner_admin.platbapartnera')),
                ('salon', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='kam_provize', to='salons.salon')),
            ],
            options={
                'verbose_name': 'provize KAM',
                'verbose_name_plural': 'provize KAM',
                'ordering': ['-obdobi', '-id'],
                'constraints': [
                    models.UniqueConstraint(
                        fields=('kam', 'salon', 'typ', 'obdobi'),
                        name='unique_kam_provize_obdobi',
                    ),
                ],
            },
        ),
    ]
