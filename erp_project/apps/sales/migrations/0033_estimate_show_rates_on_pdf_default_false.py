from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0032_estimate_show_brand_name_on_pdf_default_true'),
    ]

    operations = [
        migrations.AlterField(
            model_name='estimate',
            name='show_rates_on_pdf',
            field=models.BooleanField(
                default=False,
                help_text='If off, PDF shows description and quantity only; totals still show VAT and amount.',
            ),
        ),
    ]
