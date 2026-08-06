from django.db import migrations, models
import django.db.models.deletion


def _column_names(schema_editor, table):
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        description = connection.introspection.get_table_description(cursor, table)
    return {col.name for col in description}


def add_dual_persona_columns(apps, schema_editor):
    FlowUser = apps.get_model('flow', 'FlowUser')
    FlowSession = apps.get_model('flow', 'FlowSession')
    user_table = FlowUser._meta.db_table
    session_table = FlowSession._meta.db_table

    user_cols = _column_names(schema_editor, user_table)
    if 'pracovni_zamestnanec_id' not in user_cols:
        field = models.ForeignKey(
            blank=True,
            null=True,
            on_delete=django.db.models.deletion.SET_NULL,
            related_name='flow_pracovni_pro',
            to='rezervace.zamestnanec',
            verbose_name='pracovní persona',
        )
        field.set_attributes_from_name('pracovni_zamestnanec')
        schema_editor.add_field(FlowUser, field)

    session_cols = _column_names(schema_editor, session_table)
    if 'active_zamestnanec_id' not in session_cols:
        field = models.ForeignKey(
            blank=True,
            null=True,
            on_delete=django.db.models.deletion.SET_NULL,
            related_name='flow_aktivni_sessiony',
            to='rezervace.zamestnanec',
            verbose_name='aktivní persona',
        )
        field.set_attributes_from_name('active_zamestnanec')
        schema_editor.add_field(FlowSession, field)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('flow', '0003_customer_card'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='flowuser',
                    name='pracovni_zamestnanec',
                    field=models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='flow_pracovni_pro',
                        to='rezervace.zamestnanec',
                        verbose_name='pracovní persona',
                    ),
                ),
                migrations.AddField(
                    model_name='flowsession',
                    name='active_zamestnanec',
                    field=models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='flow_aktivni_sessiony',
                        to='rezervace.zamestnanec',
                        verbose_name='aktivní persona',
                    ),
                ),
            ],
            database_operations=[
                migrations.RunPython(add_dual_persona_columns, noop_reverse),
            ],
        ),
    ]
