"""Repurpose incoming cheque (PDCCheque) from tenant/lease to customer/project."""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('property', '0003_rentinvoice_securitydeposit'),
        ('crm', '0016_opportunity_tracking_and_trade_license_number'),
        ('projects', '0024_project_lpo_payment_terms'),
    ]

    operations = [
        # Drop the old tenant-based composite uniqueness first.
        migrations.RemoveConstraint(
            model_name='pdccheque',
            name='unique_pdc_identification',
        ),
        # Remove rent/property-specific fields (no data exists).
        migrations.RemoveField(
            model_name='pdccheque',
            name='tenant',
        ),
        migrations.RemoveField(
            model_name='pdccheque',
            name='lease',
        ),
        migrations.RemoveField(
            model_name='pdccheque',
            name='payment_period_start',
        ),
        migrations.RemoveField(
            model_name='pdccheque',
            name='payment_period_end',
        ),
        # Add customer/project links.
        migrations.AddField(
            model_name='pdccheque',
            name='customer',
            field=models.ForeignKey(
                default=None,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='pdc_cheques',
                to='crm.customer',
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='pdccheque',
            name='project',
            field=models.ForeignKey(
                blank=True,
                null=True,
                help_text='Project this cheque relates to (optional)',
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='pdc_cheques',
                to='projects.project',
            ),
        ),
        # Retarget the purpose choices to customer/project context.
        migrations.AlterField(
            model_name='pdccheque',
            name='purpose',
            field=models.CharField(
                choices=[
                    ('invoice_payment', 'Invoice Payment'),
                    ('advance', 'Customer Advance'),
                    ('retention', 'Retention Release'),
                    ('security_deposit', 'Security Deposit'),
                    ('other', 'Other'),
                ],
                default='invoice_payment',
                max_length=50,
            ),
        ),
        # Re-add composite uniqueness on customer.
        migrations.AddConstraint(
            model_name='pdccheque',
            constraint=models.UniqueConstraint(
                fields=('cheque_number', 'bank_name', 'cheque_date', 'amount', 'customer'),
                name='unique_pdc_identification',
            ),
        ),
    ]
