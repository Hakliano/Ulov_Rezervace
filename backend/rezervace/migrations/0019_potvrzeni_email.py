import uuid

from django.db import migrations, models


def prirad_potvrzeni_tokeny(apps, schema_editor):
    Rezervace = apps.get_model('rezervace', 'Rezervace')
    for rez in Rezervace.objects.all().only('id'):
        Rezervace.objects.filter(pk=rez.pk).update(potvrzeni_token=uuid.uuid4())


class Migration(migrations.Migration):

    dependencies = [
        ('rezervace', '0018_staff_prihlaseni'),
    ]

    operations = [
        migrations.AddField(
            model_name='rezervacninastaveni',
            name='potvrzeni_platnost_hodin',
            field=models.PositiveIntegerField(
                default=24,
                help_text='Po vypršení se nepotvrzená online rezervace automaticky zruší.',
                verbose_name='platnost odkazu na potvrzení (h)',
            ),
        ),
        migrations.AddField(
            model_name='rezervace',
            name='potvrzeni_exspirace',
            field=models.DateTimeField(blank=True, null=True, verbose_name='potvrzení do'),
        ),
        migrations.AddField(
            model_name='rezervace',
            name='potvrzeni_token',
            field=models.UUIDField(default=uuid.uuid4, editable=False, null=True),
        ),
        migrations.RunPython(prirad_potvrzeni_tokeny, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='rezervace',
            name='potvrzeni_token',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
        migrations.AlterField(
            model_name='rezervacninastaveni',
            name='auto_potvrzeni',
            field=models.BooleanField(
                default=False,
                help_text='Rezervace zadané zaměstnancem. Online rezervace vždy vyžadují potvrzení e-mailem.',
                verbose_name='automatické potvrzení (personál)',
            ),
        ),
    ]
