from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0004_contract_terms_and_defaults'),
    ]

    operations = [
        migrations.AddField(
            model_name='contract',
            name='scope_of_work',
            field=models.TextField(
                blank=True,
                help_text='One bullet point per line; shown on the contract PDF.',
            ),
        ),
    ]
