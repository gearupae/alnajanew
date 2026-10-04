"""Sync Company.country_code with Django model (column may already exist in DB)."""
from django.db import migrations, models


def add_country_code_column(apps, schema_editor):
    # Backend-portable + idempotent. The original RunSQL used PostgreSQL-only syntax
    # (ADD COLUMN IF NOT EXISTS, ALTER COLUMN SET DEFAULT/NOT NULL) which SQLite
    # rejects. Add the column only when it is missing.
    conn = schema_editor.connection
    table = 'settings_app_company'
    with conn.cursor() as cursor:
        existing = {c.name for c in conn.introspection.get_table_description(cursor, table)}
    if 'country_code' not in existing:
        ddl = "varchar(3) NOT NULL DEFAULT 'AE'"
        with conn.cursor() as cursor:
            cursor.execute(f'ALTER TABLE {table} ADD COLUMN country_code {ddl}')


def backfill_country_code(apps, schema_editor):
    Company = apps.get_model('settings_app', 'Company')
    mapping = {'uae': 'AE', 'ksa': 'SA', 'other': 'XX'}
    for company in Company.objects.all().iterator():
        code = mapping.get(company.country, 'AE')
        if company.country_code != code:
            company.country_code = code
            company.save(update_fields=['country_code'])


class Migration(migrations.Migration):

    dependencies = [
        ('settings_app', '0027_default_company_name_al_najah'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='company',
                    name='country_code',
                    field=models.CharField(
                        default='AE',
                        help_text='ISO country code (derived from country).',
                        max_length=3,
                    ),
                ),
            ],
            database_operations=[
                migrations.RunPython(
                    add_country_code_column,
                    migrations.RunPython.noop,
                ),
            ],
        ),
        migrations.RunPython(backfill_country_code, migrations.RunPython.noop),
    ]
