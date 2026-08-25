from django.db import migrations, models


STANDARD_TYPES = [
    'AMC',
    'Project',
    'Maintenance',
    'Service Agreement',
    'Certification',
    'NDA',
]


def seed_contract_types(apps, schema_editor):
    ContractType = apps.get_model('contracts', 'ContractType')
    for name in STANDARD_TYPES:
        ContractType.objects.get_or_create(name=name, defaults={'is_active': True})


def migrate_cancelled_to_terminated(apps, schema_editor):
    Contract = apps.get_model('contracts', 'Contract')
    Contract.objects.filter(status='cancelled').update(status='terminated')


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0005_contract_scope_of_work'),
    ]

    operations = [
        migrations.RunPython(migrate_cancelled_to_terminated, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='contract',
            name='status',
            field=models.CharField(
                choices=[
                    ('draft', 'Draft'),
                    ('upcoming', 'Upcoming'),
                    ('active', 'Active'),
                    ('expired', 'Expired'),
                    ('terminated', 'Terminated'),
                ],
                default='draft',
                help_text='Lifecycle: draft → active → expired / terminated',
                max_length=20,
            ),
        ),
        migrations.RunPython(seed_contract_types, migrations.RunPython.noop),
    ]
