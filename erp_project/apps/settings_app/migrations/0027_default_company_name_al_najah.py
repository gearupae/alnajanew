"""Set default company display name to Al Najah."""

from django.db import migrations


def rename_default_company(apps, schema_editor):
    CompanySettings = apps.get_model('settings_app', 'CompanySettings')
    CompanySettings.objects.filter(company_name='My Company').update(company_name='Al Najah')


class Migration(migrations.Migration):

    dependencies = [
        ('settings_app', '0026_inventory_approval_workflows'),
    ]

    operations = [
        migrations.RunPython(rename_default_company, migrations.RunPython.noop),
    ]
