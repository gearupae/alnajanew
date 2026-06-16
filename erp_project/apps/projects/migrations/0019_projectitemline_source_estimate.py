import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0026_estimate_revision_snapshot'),
        ('projects', '0018_project_conversion_approval'),
    ]

    operations = [
        migrations.AddField(
            model_name='projectitemline',
            name='source_estimate',
            field=models.ForeignKey(
                blank=True,
                help_text='Estimate this line was copied from (when converting quotation to project).',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='project_item_lines',
                to='sales.estimate',
            ),
        ),
    ]
