from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('flow', '0004_flow_dual_persona'),
    ]

    operations = [
        migrations.DeleteModel(
            name='CustomerVisit',
        ),
        migrations.DeleteModel(
            name='CustomerCard',
        ),
    ]
