from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('partner_admin', '0018_partneradminprofil'),
        ('salons', '0008_cenikpolozka_rizikovy'),
    ]

    operations = [
        migrations.AddField(
            model_name='partnernastaveni',
            name='plan',
            field=models.CharField(
                choices=[('start', 'START'), ('pro', 'PRO')],
                db_index=True,
                default='pro',
                help_text=(
                    'Funkční oprávnění partnera (START / PRO). '
                    'Nesouvisí s billingovým tarifem, cenou ani fakturací.'
                ),
                max_length=16,
                verbose_name='produktový plán',
            ),
        ),
        migrations.CreateModel(
            name='PartnerFeatureGrant',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('feature', models.CharField(db_index=True, max_length=64, verbose_name='feature kód')),
                ('zakaz', models.BooleanField(
                    default=False,
                    help_text='Zapnuto = tuto funkci partner nesmí používat, i když ji má v plánu.',
                    verbose_name='zákaz',
                )),
                ('platnost_od', models.DateTimeField(blank=True, null=True, verbose_name='platnost od')),
                ('platnost_do', models.DateTimeField(blank=True, null=True, verbose_name='platnost do')),
                ('zdroj', models.CharField(
                    choices=[('trial', 'Trial'), ('vyjimka', 'Výjimka'), ('test', 'Test')],
                    default='vyjimka',
                    max_length=32,
                    verbose_name='zdroj',
                )),
                ('poznamka', models.CharField(blank=True, max_length=300, verbose_name='poznámka')),
                ('aktivni', models.BooleanField(db_index=True, default=True, verbose_name='aktivní')),
                ('vytvoreno', models.DateTimeField(auto_now_add=True)),
                ('aktualizovano', models.DateTimeField(auto_now=True)),
                ('salon', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='feature_grants',
                    to='salons.salon',
                )),
            ],
            options={
                'verbose_name': 'grant / zákaz feature',
                'verbose_name_plural': 'granty / zákazy features',
                'ordering': ['-vytvoreno'],
            },
        ),
        migrations.AddIndex(
            model_name='partnerfeaturegrant',
            index=models.Index(fields=['salon', 'feature', 'aktivni'], name='partner_adm_salon_i_feat_idx'),
        ),
    ]
