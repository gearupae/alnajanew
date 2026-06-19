from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0026_estimate_revision_snapshot'),
    ]

    operations = [
        migrations.AddField(
            model_name='estimate',
            name='edit_approval_rejection_reason',
            field=models.TextField(blank=True),
        ),
    ]
