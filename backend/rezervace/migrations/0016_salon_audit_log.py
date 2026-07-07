from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('salons', '0001_initial'),
        ('rezervace', '0015_gdpr_anonymizace'),
    ]

    operations = [
        migrations.CreateModel(
            name='SalonAuditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kdo', models.CharField(max_length=100, verbose_name='kdo')),
                ('kdy', models.DateTimeField(auto_now_add=True)),
                ('kategorie', models.CharField(max_length=50, verbose_name='kategorie')),
                ('popis', models.TextField(verbose_name='popis')),
                ('objekt_typ', models.CharField(blank=True, max_length=50, verbose_name='typ objektu')),
                ('objekt_id', models.IntegerField(blank=True, null=True)),
                ('data_pred', models.JSONField(blank=True, null=True)),
                ('data_po', models.JSONField(blank=True, null=True)),
                ('salon', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='audit_log', to='salons.salon')),
            ],
            options={
                'verbose_name': 'audit log',
                'verbose_name_plural': 'audit log',
                'ordering': ['-kdy'],
            },
        ),
    ]
