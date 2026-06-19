from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('purchase', '0020_pr_attachment_vendor_ref_optional_file'),
    ]

    operations = [
        migrations.AddField(
            model_name='purchaserequest',
            name='vendor',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='purchase_requests',
                to='purchase.vendor',
            ),
        ),
    ]
