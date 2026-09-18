from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('purchase', '0029_expenseclaim_project'),
    ]

    operations = [
        migrations.AddField(
            model_name='vendorbill',
            name='discount_applied',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('0.00'),
                help_text='Last calculated discount amount on subtotal (excl. VAT)',
                max_digits=15,
            ),
        ),
        migrations.AddField(
            model_name='vendorbill',
            name='discount_type',
            field=models.CharField(
                choices=[('none', 'None'), ('percent', 'Percentage'), ('amount', 'Fixed amount')],
                default='none',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='vendorbill',
            name='discount_value',
            field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=15),
        ),
        migrations.AddField(
            model_name='vendorbill',
            name='round_off',
            field=models.DecimalField(
                decimal_places=2,
                default=Decimal('0.00'),
                help_text='Adjustment applied to grand total (e.g. fils rounding)',
                max_digits=15,
            ),
        ),
    ]
