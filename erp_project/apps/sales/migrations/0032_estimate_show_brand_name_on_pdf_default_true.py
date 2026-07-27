from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0031_vat_inclusive_pricing'),
    ]

    operations = [
        migrations.AlterField(
            model_name='estimate',
            name='show_brand_name_on_pdf',
            field=models.BooleanField(
                default=True,
                help_text='If on, PDF shows the inventory item brand name on each line.',
            ),
        ),
    ]
