from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0036_alter_accountmapping_security_cheque_forfeiture'),
    ]

    operations = [
        migrations.AlterField(
            model_name='bankaccount',
            name='account_number',
            field=models.CharField(blank=True, default='', max_length=50),
        ),
    ]
