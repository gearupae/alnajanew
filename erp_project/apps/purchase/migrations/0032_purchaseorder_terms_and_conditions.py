from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('purchase', '0031_purchaseorder_vat_roundoff'),
    ]

    operations = [
        migrations.AddField(
            model_name='purchaseorder',
            name='terms_and_conditions',
            field=models.TextField(
                blank=True,
                help_text='Terms and conditions printed on the purchase order PDF.',
            ),
        ),
    ]
