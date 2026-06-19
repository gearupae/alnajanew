from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0020_project_operation_access'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='conversion_approval_rejection_reason',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='project',
            name='edit_approval_rejection_reason',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='project',
            name='operation_access_rejection_reason',
            field=models.TextField(blank=True),
        ),
    ]
