from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('purchase', '0019_po_goods_receiving'),
    ]

    operations = [
        migrations.AddField(
            model_name='purchaserequestattachment',
            name='vendor_ref',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='purchase_request_quotes',
                to='purchase.vendor',
            ),
        ),
        migrations.AlterField(
            model_name='purchaserequestattachment',
            name='file',
            field=models.FileField(
                blank=True,
                null=True,
                upload_to='purchase_request_attachments/%Y/%m/',
            ),
        ),
    ]
