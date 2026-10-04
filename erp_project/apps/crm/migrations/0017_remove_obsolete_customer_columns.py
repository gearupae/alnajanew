"""Drop legacy DB columns not present on the Customer model."""

from django.db import migrations


def drop_obsolete_columns(apps, schema_editor):
    # Backend-portable + idempotent: `DROP COLUMN IF EXISTS` is PostgreSQL-only
    # (SQLite rejects the IF EXISTS clause), so introspect and drop only the
    # columns that are actually present. Safe on a DB that never had them.
    conn = schema_editor.connection
    table = 'crm_customer'
    obsolete = ('cr_number', 'billboard', 'billboard_document')
    with conn.cursor() as cursor:
        existing = {c.name for c in conn.introspection.get_table_description(cursor, table)}
    for column in obsolete:
        if column not in existing:
            continue
        with conn.cursor() as cursor:
            cursor.execute(f'ALTER TABLE {table} DROP COLUMN {column}')


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0016_opportunity_tracking_and_trade_license_number'),
    ]

    operations = [
        migrations.RunPython(drop_obsolete_columns, migrations.RunPython.noop),
    ]
