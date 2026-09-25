from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0035_invoice_document_title'),
    ]

    operations = [
        migrations.AddField(
            model_name='estimate',
            name='round_off',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('0.00'),
                help_text='Adjustment applied to grand total (e.g. fils rounding)',
                max_digits=15,
            ),
        ),
    ]
