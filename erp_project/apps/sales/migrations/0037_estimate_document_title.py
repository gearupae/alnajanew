from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0036_estimate_round_off'),
    ]

    operations = [
        migrations.AddField(
            model_name='estimate',
            name='document_title',
            field=models.CharField(
                default='QUOTATION',
                help_text='Heading shown on the quotation PDF title bar',
                max_length=100,
            ),
        ),
    ]
