from django.db import migrations, models

from rezervace.services.gdpr import email_hash


def dopln_email_hash(apps, schema_editor):
    Zakaznik = apps.get_model('rezervace', 'Zakaznik')
    for z in Zakaznik.objects.exclude(email=''):
        if not z.email_hash and '@' in (z.email or ''):
            z.email_hash = email_hash(z.email)
            z.save(update_fields=['email_hash'])
    NoShowZaznam = apps.get_model('rezervace', 'NoShowZaznam')
    for n in NoShowZaznam.objects.exclude(email=''):
        if not n.email_hash and n.email:
            n.email_hash = email_hash(n.email)
            n.save(update_fields=['email_hash'])


class Migration(migrations.Migration):

    dependencies = [
        ('rezervace', '0014_noshow_gdpr_text'),
    ]

    operations = [
        migrations.AddField(
            model_name='rezervace',
            name='anonymizovano',
            field=models.BooleanField(default=False, verbose_name='anonymizováno (GDPR)'),
        ),
        migrations.AddField(
            model_name='rezervace',
            name='anonymizovano_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='anonymizováno kdy'),
        ),
        migrations.AddField(
            model_name='zakaznik',
            name='email_hash',
            field=models.CharField(blank=True, db_index=True, max_length=64, verbose_name='hash e-mailu'),
        ),
        migrations.AddField(
            model_name='noshowzaznam',
            name='email_hash',
            field=models.CharField(blank=True, db_index=True, max_length=64, verbose_name='hash e-mailu'),
        ),
        migrations.AlterField(
            model_name='noshowzaznam',
            name='email',
            field=models.EmailField(blank=True, max_length=254, verbose_name='e-mail'),
        ),
        migrations.RunPython(dopln_email_hash, migrations.RunPython.noop),
    ]
