from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('partner_admin', '0019_partner_plan_feature_grants'),
    ]

    operations = [
        migrations.AlterField(
            model_name='potencialnikontakt',
            name='stav',
            field=models.CharField(
                choices=[
                    ('lead_pred_webu', 'Lead před kontrolou webu'),
                    ('lead_po_webu', 'Lead po kontrole webu'),
                    ('kontakt_email', 'Kontaktován e-mailem'),
                    ('kontakt_sms', 'Kontaktován SMS'),
                    ('kontakt_telefon', 'Kontaktován telefonicky'),
                    ('kontakt_osobne', 'Kontaktován osobně'),
                    ('nefunkcni_telefon', 'Nefunkční telefon'),
                    ('zavolat_znovu', 'Zavolat znovu'),
                    ('ozvat_se_pozdeji', 'Ozvat se později'),
                    ('domluvena_schuzka', 'Domluvená schůzka'),
                    ('nema_zajem', 'Nemá zájem'),
                    ('ma_zajem', 'Má zájem'),
                    ('prodano', 'Prodáno'),
                    ('nechceme', 'Nechceme'),
                ],
                db_index=True,
                default='lead_pred_webu',
                max_length=32,
                verbose_name='stav',
            ),
        ),
    ]
