# POS invoice columns may already exist on some databases (applied out-of-band on
# the original instance). This migration adds any that are missing, idempotently and
# in a backend-portable way, so it is safe on a fresh DB (SQLite or PostgreSQL) and
# on a DB where the columns already exist.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


# column name -> (sqlite DDL, postgresql DDL). Types mirror the state fields below.
_POS_COLUMNS = {
    'source': ("varchar(20) NOT NULL DEFAULT 'standard'",
               "varchar(20) NOT NULL DEFAULT 'standard'"),
    'pos_payment_method': ("varchar(30) NOT NULL DEFAULT 'cash'",
                           "varchar(30) NOT NULL DEFAULT 'cash'"),
    'pos_location': ("varchar(500) NOT NULL DEFAULT ''",
                     "varchar(500) NOT NULL DEFAULT ''"),
    'pos_salesperson_name': ("varchar(200) NOT NULL DEFAULT ''",
                             "varchar(200) NOT NULL DEFAULT ''"),
    'pos_salesperson_id': ("bigint NULL", "bigint NULL"),
    'pos_warehouse_id': ("bigint NULL", "bigint NULL"),
    'pos_whatsapp_phone': ("varchar(30) NOT NULL DEFAULT ''",
                           "varchar(30) NOT NULL DEFAULT ''"),
    'pos_whatsapp_shared': ("bool NOT NULL DEFAULT 0",
                            "boolean NOT NULL DEFAULT false"),
    'pos_whatsapp_shared_at': ("datetime NULL", "timestamp with time zone NULL"),
    'pos_whatsapp_shared_by_id': ("bigint NULL", "bigint NULL"),
}


def add_missing_pos_columns(apps, schema_editor):
    conn = schema_editor.connection
    table = 'sales_invoice'
    with conn.cursor() as cursor:
        existing = {c.name for c in conn.introspection.get_table_description(cursor, table)}
    for column, (sqlite_ddl, pg_ddl) in _POS_COLUMNS.items():
        if column in existing:
            continue
        ddl = sqlite_ddl if conn.vendor == 'sqlite' else pg_ddl
        with conn.cursor() as cursor:
            cursor.execute(f'ALTER TABLE {table} ADD COLUMN {column} {ddl}')


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0001_initial'),
        ('hr', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('sales', '0037_estimate_document_title'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    add_missing_pos_columns,
                    migrations.RunPython.noop,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='invoice',
                    name='source',
                    field=models.CharField(
                        choices=[('standard', 'Standard'), ('pos', 'Point of sale')],
                        default='standard',
                        help_text='How this invoice was created (standard sales vs POS).',
                        max_length=20,
                    ),
                ),
                migrations.AddField(
                    model_name='invoice',
                    name='pos_payment_method',
                    field=models.CharField(
                        default='cash',
                        help_text='Payment method when created from POS (cash, card, etc.).',
                        max_length=30,
                    ),
                ),
                migrations.AddField(
                    model_name='invoice',
                    name='pos_location',
                    field=models.CharField(blank=True, default='', max_length=500),
                ),
                migrations.AddField(
                    model_name='invoice',
                    name='pos_salesperson_name',
                    field=models.CharField(blank=True, default='', max_length=200),
                ),
                migrations.AddField(
                    model_name='invoice',
                    name='pos_salesperson',
                    field=models.ForeignKey(
                        blank=True,
                        db_column='pos_salesperson_id',
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='pos_invoices',
                        to='hr.employee',
                    ),
                ),
                migrations.AddField(
                    model_name='invoice',
                    name='pos_warehouse',
                    field=models.ForeignKey(
                        blank=True,
                        db_column='pos_warehouse_id',
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='pos_invoices',
                        to='inventory.warehouse',
                    ),
                ),
                migrations.AddField(
                    model_name='invoice',
                    name='pos_whatsapp_phone',
                    field=models.CharField(blank=True, default='', max_length=30),
                ),
                migrations.AddField(
                    model_name='invoice',
                    name='pos_whatsapp_shared',
                    field=models.BooleanField(default=False),
                ),
                migrations.AddField(
                    model_name='invoice',
                    name='pos_whatsapp_shared_at',
                    field=models.DateTimeField(blank=True, null=True),
                ),
                migrations.AddField(
                    model_name='invoice',
                    name='pos_whatsapp_shared_by',
                    field=models.ForeignKey(
                        blank=True,
                        db_column='pos_whatsapp_shared_by_id',
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='invoices_whatsapp_shared',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
    ]
