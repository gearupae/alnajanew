import uuid

from django.db import migrations, models


def assign_public_view_tokens(apps, schema_editor):
    Estimate = apps.get_model('sales', 'Estimate')
    for row in Estimate.objects.all().iterator():
        row.public_view_token = uuid.uuid4()
        row.save(update_fields=['public_view_token'])


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0027_estimate_edit_approval_rejection_reason'),
    ]

    operations = [
        migrations.AddField(
            model_name='estimate',
            name='public_view_count',
            field=models.PositiveIntegerField(
                default=0,
                help_text='Number of times the public quotation link was opened.',
            ),
        ),
        migrations.AddField(
            model_name='estimate',
            name='public_view_token',
            field=models.UUIDField(
                editable=False,
                help_text='Secret token for the customer-facing quotation URL (no login).',
                null=True,
            ),
        ),
        migrations.RunPython(assign_public_view_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='estimate',
            name='public_view_token',
            field=models.UUIDField(
                default=uuid.uuid4,
                editable=False,
                help_text='Secret token for the customer-facing quotation URL (no login).',
                unique=True,
            ),
        ),
    ]
