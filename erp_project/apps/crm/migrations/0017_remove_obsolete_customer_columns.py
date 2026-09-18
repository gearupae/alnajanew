"""Drop legacy DB columns not present on the Customer model."""

from django.db import migrations


def drop_obsolete_columns(apps, schema_editor):
    table = 'crm_customer'
    obsolete = ('cr_number', 'billboard', 'billboard_document')
    with schema_editor.connection.cursor() as cursor:
        for column in obsolete:
            cursor.execute(
                f'ALTER TABLE {table} DROP COLUMN IF EXISTS {column};'
            )


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0016_opportunity_tracking_and_trade_license_number'),
    ]

    operations = [
        migrations.RunPython(drop_obsolete_columns, migrations.RunPython.noop),
    ]
