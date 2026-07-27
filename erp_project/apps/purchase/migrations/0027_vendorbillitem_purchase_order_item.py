from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('purchase', '0026_purchaserequest_service_request'),
    ]

    operations = [
        migrations.AddField(
            model_name='vendorbillitem',
            name='purchase_order_item',
            field=models.ForeignKey(
                blank=True,
                help_text='PO line this bill row bills against (partial billing by received qty).',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='vendor_bill_lines',
                to='purchase.purchaseorderitem',
            ),
        ),
    ]
