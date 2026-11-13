from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0040_creditnoteline_optional_invoice_line'),
    ]

    operations = [
        migrations.AlterField(
            model_name='invoice',
            name='due_date',
            field=models.DateField(blank=True, null=True),
        ),
    ]
