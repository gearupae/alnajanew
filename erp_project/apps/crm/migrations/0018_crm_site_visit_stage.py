"""Site Visit kanban stage flag + default pipeline column."""

from django.db import migrations, models


def seed_site_visit_stage(apps, schema_editor):
    CrmLeadKanbanStage = apps.get_model('crm', 'CrmLeadKanbanStage')
    CrmLeadKanbanStage.objects.get_or_create(
        slug='site-visit',
        defaults={
            'name': 'Site Visit',
            'sort_order': 12,
            'is_active': True,
            'converts_to_customer': False,
            'tracks_opportunity': False,
            'is_site_visit': True,
        },
    )


class Migration(migrations.Migration):

    dependencies = [
        ('crm', '0017_remove_obsolete_customer_columns'),
    ]

    operations = [
        migrations.AddField(
            model_name='crmleadkanbanstage',
            name='is_site_visit',
            field=models.BooleanField(
                default=False,
                help_text='Leads moved here are treated as site visits; assignees get a “Site visit pending” notification.',
            ),
        ),
        migrations.RunPython(seed_site_visit_stage, migrations.RunPython.noop),
    ]
