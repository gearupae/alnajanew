from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('purchase', '0027_vendorbillitem_purchase_order_item'),
    ]

    operations = [
        migrations.AddField(
            model_name='vendor',
            name='website',
            field=models.URLField(blank=True, max_length=500),
        ),
        migrations.AddField(
            model_name='vendor',
            name='trn_document',
            field=models.FileField(
                blank=True,
                help_text='Optional. VAT/TRN certificate (PDF or image).',
                max_length=500,
                upload_to='purchase/vendor_documents/%Y/%m/',
                verbose_name='TRN document',
            ),
        ),
        migrations.AddField(
            model_name='vendor',
            name='trade_license_document',
            field=models.FileField(
                blank=True,
                help_text='Optional. Trade license (PDF or image).',
                max_length=500,
                upload_to='purchase/vendor_documents/%Y/%m/',
                verbose_name='Trade license',
            ),
        ),
    ]
