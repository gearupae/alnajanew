from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('purchase', '0023_purchaserequest_project'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='purchaserequest',
            name='project',
        ),
    ]
