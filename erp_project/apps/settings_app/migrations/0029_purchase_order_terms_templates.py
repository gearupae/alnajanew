from django.db import migrations, models


def migrate_legacy_po_terms_default(apps, schema_editor):
    CompanySettings = apps.get_model('settings_app', 'CompanySettings')
    PurchaseOrderTermsTemplate = apps.get_model('settings_app', 'PurchaseOrderTermsTemplate')

    cs = CompanySettings.objects.filter(pk=1).first()
    if not cs:
        return
    body = (getattr(cs, 'contract_default_terms', None) or '').strip()
    if body:
        PurchaseOrderTermsTemplate.objects.create(
            name='Default',
            body=body,
            is_default=True,
            sort_order=0,
            is_active=True,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('settings_app', '0028_company_country_code'),
    ]

    operations = [
        migrations.CreateModel(
            name='PurchaseOrderTermsTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120)),
                ('body', models.TextField(blank=True)),
                ('is_default', models.BooleanField(default=False, help_text='Pre-selected when creating a new purchase order (only one default).')),
                ('sort_order', models.PositiveIntegerField(default=0)),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={
                'verbose_name': 'Purchase order terms template',
                'verbose_name_plural': 'Purchase order terms templates',
                'ordering': ['sort_order', 'name'],
            },
        ),
        migrations.RunPython(migrate_legacy_po_terms_default, migrations.RunPython.noop),
    ]
