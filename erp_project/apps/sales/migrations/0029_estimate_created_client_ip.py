from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales', '0028_estimate_public_view_link'),
    ]

    operations = [
        migrations.AddField(
            model_name='estimate',
            name='created_client_ip',
            field=models.CharField(
                blank=True,
                default='',
                help_text='Client IP when this quotation was created (public views from same IP are not counted).',
                max_length=45,
            ),
        ),
    ]
