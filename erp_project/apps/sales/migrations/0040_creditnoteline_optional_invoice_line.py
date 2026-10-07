from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0039_invoiceitem_inventory_item'),
    ]

    operations = [
        migrations.AlterField(
            model_name='creditnoteline',
            name='invoice_line',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='credit_note_lines',
                to='sales.invoiceitem',
            ),
        ),
    ]
