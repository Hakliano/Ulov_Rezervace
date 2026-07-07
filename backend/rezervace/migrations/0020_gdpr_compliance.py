# Generated manually for GDPR compliance

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('salons', '0004_cenikpolozka_aktivni_cenikpolozka_delka_minut_and_more'),
        ('rezervace', '0019_potvrzeni_email'),
    ]

    operations = [
        migrations.AddField(
            model_name='rezervacninastaveni',
            name='gdpr_zasady_verze',
            field=models.CharField(
                default='1.0',
                help_text='Aktuální verze zobrazená zákazníkům (např. 1.0, 1.2).',
                max_length=20,
                verbose_name='verze Zásad ochrany osobních údajů',
            ),
        ),
        migrations.AddField(
            model_name='rezervacninastaveni',
            name='uchovavani_mesicu',
            field=models.PositiveIntegerField(
                default=12,
                help_text='Po anonymizaci — jak dlouho zůstanou záznamy pro statistiky, než budou smazány.',
                verbose_name='doba uchování dat (měsíce)',
            ),
        ),
        migrations.AddField(
            model_name='zakaznik',
            name='gdpr_ip',
            field=models.GenericIPAddressField(blank=True, null=True, verbose_name='IP při souhlasu'),
        ),
        migrations.AddField(
            model_name='zakaznik',
            name='gdpr_zasady_verze',
            field=models.CharField(blank=True, max_length=20, verbose_name='verze zásad GDPR'),
        ),
        migrations.CreateModel(
            name='SouhlasGDPR',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email', models.EmailField(blank=True, max_length=254, verbose_name='e-mail')),
                ('typ', models.CharField(choices=[('rezervace', 'Online rezervace'), ('registrace', 'Registrace účtu')], max_length=20, verbose_name='typ')),
                ('zasady_verze', models.CharField(max_length=20, verbose_name='verze zásad')),
                ('jazyk', models.CharField(default='cs', max_length=10, verbose_name='jazyk')),
                ('ip_adresa', models.GenericIPAddressField(blank=True, null=True, verbose_name='IP adresa')),
                ('user_agent', models.CharField(blank=True, max_length=300, verbose_name='user-agent')),
                ('vytvoreno', models.DateTimeField(auto_now_add=True)),
                ('rezervace', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='souhlasy_gdpr', to='rezervace.rezervace')),
                ('salon', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='souhlasy_gdpr', to='salons.salon')),
                ('zakaznik', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='souhlasy_gdpr', to='rezervace.zakaznik')),
            ],
            options={
                'verbose_name': 'souhlas GDPR',
                'verbose_name_plural': 'souhlasy GDPR',
                'ordering': ['-vytvoreno'],
            },
        ),
    ]
