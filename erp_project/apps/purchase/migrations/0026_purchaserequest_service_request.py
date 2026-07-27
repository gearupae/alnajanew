from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('service_request', '0001_initial'),
        ('purchase', '0025_debit_notes'),
    ]

    operations = [
        migrations.AddField(
            model_name='purchaserequest',
            name='service_request',
            field=models.ForeignKey(
                blank=True,
                help_text='Optional source service request (create only).',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='purchase_requests',
                to='service_request.servicerequest',
            ),
        ),
    ]
