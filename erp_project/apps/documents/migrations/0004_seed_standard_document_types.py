from django.db import migrations

STANDARD_TYPES = [
    ('Trade License', 'Commercial / trade license renewal', 60),
    ('Insurance', 'General liability, professional indemnity, or policy certificate', 30),
    ('Visa', 'Employment or residence visa', 60),
    ('Emirates ID', 'Emirates ID card', 30),
    ('Certification', 'ISO, safety, or professional certification', 30),
    ('Value Added Certification', 'VAT or other value-added tax registration certificate', 30),
    ('Work Permit', 'Labour card / work permit', 30),
    ('Passport', 'Passport copy on file', 60),
]


def seed_document_types(apps, schema_editor):
    DocumentType = apps.get_model('documents', 'DocumentType')
    for name, description, alert_days in STANDARD_TYPES:
        DocumentType.objects.get_or_create(
            name=name,
            defaults={
                'description': description,
                'alert_days_before': alert_days,
                'is_active': True,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0003_document_type_optional_alert_days'),
    ]

    operations = [
        migrations.RunPython(seed_document_types, migrations.RunPython.noop),
    ]
