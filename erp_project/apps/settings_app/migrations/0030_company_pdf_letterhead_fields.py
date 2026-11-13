from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('settings_app', '0029_purchase_order_terms_templates'),
    ]

    operations = [
        migrations.AddField(
            model_name='companysettings',
            name='pdf_letterhead_subtitle',
            field=models.CharField(
                blank=True,
                help_text='English line under the PDF letterhead (e.g. regulatory approval text).',
                max_length=200,
            ),
        ),
        migrations.AddField(
            model_name='companysettings',
            name='pdf_letterhead_subtitle_ar',
            field=models.CharField(
                blank=True,
                help_text='Arabic line shown on the PDF letterhead.',
                max_length=200,
            ),
        ),
        migrations.AddField(
            model_name='companysettings',
            name='pdf_footer_services',
            field=models.CharField(
                blank=True,
                help_text='Services shown on the PDF footer bar, separated by | (pipe).',
                max_length=500,
            ),
        ),
        migrations.AddField(
            model_name='companysettings',
            name='pdf_services_badge_label',
            field=models.CharField(
                blank=True,
                default='LPG Services',
                help_text='Short badge label on the PDF footer services bar.',
                max_length=80,
            ),
        ),
    ]
