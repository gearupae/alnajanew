from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0034_invoice_discount_roundoff'),
    ]

    operations = [
        migrations.AddField(
            model_name='invoice',
            name='document_title',
            field=models.CharField(
                default='TAX INVOICE',
                help_text='Heading shown on the invoice PDF title bar',
                max_length=100,
            ),
        ),
    ]
