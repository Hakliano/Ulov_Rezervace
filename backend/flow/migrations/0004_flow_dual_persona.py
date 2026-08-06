from django.db import migrations, models
import django.db.models.deletion


def _column_names(schema_editor, table):
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        description = connection.introspection.get_table_description(cursor, table)
    return {col.name for col in description}


def add_dual_persona_columns(apps, schema_editor):
    """Raw SQL — historical FK přes schema_editor.add_field v RunPython selhává."""
    user_table = 'flow_flowuser'
    session_table = 'flow_flowsession'
    user_cols = _column_names(schema_editor, user_table)
    session_cols = _column_names(schema_editor, session_table)

    with schema_editor.connection.cursor() as cursor:
        if 'pracovni_zamestnanec_id' not in user_cols:
            cursor.execute(
                f'ALTER TABLE {user_table} '
                'ADD COLUMN pracovni_zamestnanec_id integer NULL '
                'CONSTRAINT flow_flowuser_pracovni_zamestnanec_id_fk '
                'REFERENCES rezervace_zamestnanec(id) '
                'DEFERRABLE INITIALLY DEFERRED'
            )
            cursor.execute(
                f'CREATE INDEX IF NOT EXISTS flow_flowuser_pracovni_zam_idx '
                f'ON {user_table} (pracovni_zamestnanec_id)'
            )
        if 'active_zamestnanec_id' not in session_cols:
            cursor.execute(
                f'ALTER TABLE {session_table} '
                'ADD COLUMN active_zamestnanec_id integer NULL '
                'CONSTRAINT flow_flowsession_active_zamestnanec_id_fk '
                'REFERENCES rezervace_zamestnanec(id) '
                'DEFERRABLE INITIALLY DEFERRED'
            )
            cursor.execute(
                f'CREATE INDEX IF NOT EXISTS flow_flowsession_active_zam_idx '
                f'ON {session_table} (active_zamestnanec_id)'
            )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('flow', '0003_customer_card'),
        ('rezervace', '0032_unique_owner_login_email'),
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
