from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('projects', '0021_project_approval_rejection_reasons'),
        ('advances', '0002_security_cheque_vendor_fk'),
    ]

    operations = [
        migrations.AddField(
            model_name='customeradvance',
            name='project',
            field=models.ForeignKey(
                blank=True,
                help_text='Optional project this advance relates to.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='customer_advances',
                to='projects.project',
            ),
        ),
    ]
