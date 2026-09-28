# POS invoice columns already exist on some databases (applied outside this repo).
# State-only sync so Django knows about them; skip ALTER when columns are present.

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0001_initial'),
        ('hr', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('sales', '0037_estimate_document_title'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AddField(
                    model_name='invoice',
                    name='source',
                    field=models.CharField(
                        choices=[('standard', 'Standard'), ('pos', 'Point of sale')],
                        default='standard',
                        help_text='How this invoice was created (standard sales vs POS).',
                        max_length=20,
                    ),
                ),
                migrations.AddField(
                    model_name='invoice',
                    name='pos_payment_method',
                    field=models.CharField(
                        default='cash',
                        help_text='Payment method when created from POS (cash, card, etc.).',
                        max_length=30,
                    ),
                ),
                migrations.AddField(
                    model_name='invoice',
                    name='pos_location',
                    field=models.CharField(blank=True, default='', max_length=500),
                ),
                migrations.AddField(
                    model_name='invoice',
                    name='pos_salesperson_name',
                    field=models.CharField(blank=True, default='', max_length=200),
                ),
                migrations.AddField(
                    model_name='invoice',
                    name='pos_salesperson',
                    field=models.ForeignKey(
                        blank=True,
                        db_column='pos_salesperson_id',
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='pos_invoices',
                        to='hr.employee',
                    ),
                ),
                migrations.AddField(
                    model_name='invoice',
                    name='pos_warehouse',
                    field=models.ForeignKey(
                        blank=True,
                        db_column='pos_warehouse_id',
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='pos_invoices',
                        to='inventory.warehouse',
                    ),
                ),
                migrations.AddField(
                    model_name='invoice',
                    name='pos_whatsapp_phone',
                    field=models.CharField(blank=True, default='', max_length=30),
                ),
                migrations.AddField(
                    model_name='invoice',
                    name='pos_whatsapp_shared',
                    field=models.BooleanField(default=False),
                ),
                migrations.AddField(
                    model_name='invoice',
                    name='pos_whatsapp_shared_at',
                    field=models.DateTimeField(blank=True, null=True),
                ),
                migrations.AddField(
                    model_name='invoice',
                    name='pos_whatsapp_shared_by',
                    field=models.ForeignKey(
                        blank=True,
                        db_column='pos_whatsapp_shared_by_id',
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='invoices_whatsapp_shared',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
    ]
