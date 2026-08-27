from django.conf import settings
from django.db import migrations, models
from django.utils import timezone


def backfill_zalozeno(apps, schema_editor):
    PartnerNastaveniHist = apps.get_model('partner_admin', 'PartnerNastaveni')
    Platba = apps.get_model('partner_admin', 'PlatbaPartnera')
    for partner in PartnerNastaveniHist.objects.all():
        prvni = (
            Platba.objects.filter(salon_id=partner.salon_id)
            .order_by('vytvoreno')
            .values_list('vytvoreno', flat=True)
            .first()
        )
        if prvni:
            partner.zalozeno = prvni
            partner.save(update_fields=['zalozeno'])


class Migration(migrations.Migration):

    dependencies = [
        ('partner_admin', '0008_partnertarif'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='partnernastaveni',
            name='zalozeno',
            field=models.DateTimeField(db_index=True, default=timezone.now, editable=False, verbose_name='založeno'),
        ),
        migrations.AddField(
            model_name='technickachyba',
            name='query',
            field=models.CharField(blank=True, max_length=400, verbose_name='query bez tajemství'),
        ),
        migrations.AddField(
            model_name='technickachyba',
            name='status_kod',
            field=models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='HTTP stav'),
        ),
        migrations.AddField(
            model_name='technickachyba',
            name='stopa',
            field=models.TextField(blank=True, verbose_name='traceback'),
        ),
        migrations.AlterField(
            model_name='technickachyba',
            name='detail',
            field=models.TextField(blank=True),
        ),
        migrations.CreateModel(
            name='HromadnyEmail',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('predmet', models.CharField(max_length=200)),
                ('text', models.TextField()),
                ('okruh', models.CharField(choices=[('vsichni', 'Všichni partneři s e-mailem'), ('po_splatnosti', 'Jen po splatnosti'), ('active', 'Jen ACTIVE'), ('tarif', 'Podle tarifu')], default='vsichni', max_length=20)),
                ('tarif', models.CharField(blank=True, max_length=100)),
                ('odeslano_pocet', models.PositiveIntegerField(default=0)),
                ('preskoceno_pocet', models.PositiveIntegerField(default=0)),
                ('chyba_pocet', models.PositiveIntegerField(default=0)),
                ('vytvoreno', models.DateTimeField(auto_now_add=True)),
                ('odeslal', models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, related_name='hromadne_emaily', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'hromadný e-mail',
                'verbose_name_plural': 'hromadné e-maily',
                'ordering': ['-vytvoreno'],
            },
        ),
        migrations.RunPython(backfill_zalozeno, migrations.RunPython.noop),
    ]
