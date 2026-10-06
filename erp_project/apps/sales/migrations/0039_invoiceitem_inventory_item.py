from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0022_alter_item_options'),
        ('sales', '0038_invoice_pos_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='invoiceitem',
            name='inventory_item',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='invoice_lines',
                to='inventory.item',
            ),
        ),
    ]
