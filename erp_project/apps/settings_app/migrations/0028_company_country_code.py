"""Sync Company.country_code with Django model (column may already exist in DB)."""
from django.db import migrations, models


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
                migrations.RunSQL(
                    sql="""
                    ALTER TABLE settings_app_company
                    ADD COLUMN IF NOT EXISTS country_code varchar(3);
                    UPDATE settings_app_company
                    SET country_code = CASE country
                        WHEN 'uae' THEN 'AE'
                        WHEN 'ksa' THEN 'SA'
                        ELSE 'XX'
                    END
                    WHERE country_code IS NULL OR country_code = '';
                    ALTER TABLE settings_app_company
                    ALTER COLUMN country_code SET DEFAULT 'AE';
                    UPDATE settings_app_company
                    SET country_code = 'AE'
                    WHERE country_code IS NULL;
                    ALTER TABLE settings_app_company
                    ALTER COLUMN country_code SET NOT NULL;
                    """,
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
        ),
        migrations.RunPython(backfill_country_code, migrations.RunPython.noop),
    ]
