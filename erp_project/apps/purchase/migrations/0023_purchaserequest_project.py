from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0021_project_approval_rejection_reasons'),
        ('purchase', '0022_purchaseorder_project'),
    ]

    operations = [
        migrations.AddField(
            model_name='purchaserequest',
            name='project',
            field=models.ForeignKey(
                blank=True,
                help_text='Optional project to charge purchased items against.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='purchase_requests',
                to='projects.project',
            ),
        ),
    ]
