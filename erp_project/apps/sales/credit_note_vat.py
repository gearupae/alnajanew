"""VAT return helpers for posted sales tax credit notes."""
from decimal import Decimal

from django.db.models import Sum

from .models import CreditNote, CreditNoteLine


def credit_note_period_adjustments(period_start, period_end):
    """
    Return (supplies_reduction, vat_reduction, audit_rows) for posted credit notes
    in the issue date period.
    """
    posted = CreditNote.objects.filter(
        is_active=True,
        status='posted',
        issue_date__gte=period_start,
        issue_date__lte=period_end,
    ).select_related('customer', 'original_invoice')

    lines = CreditNoteLine.objects.filter(
        credit_note__in=posted,
        vat_rate__gt=0,
    )

    supplies_reduction = lines.aggregate(total=Sum('line_total'))['total'] or Decimal('0.00')
    vat_reduction = lines.aggregate(total=Sum('line_vat'))['total'] or Decimal('0.00')

    audit_rows = [
        {
            'number': cn.number,
            'customer_name': cn.customer.name,
            'issue_date': cn.issue_date,
            'trigger_event_date': cn.trigger_event_date,
            'original_invoice': cn.original_invoice.invoice_number,
            'reason': cn.get_reason_display(),
            'subtotal': cn.subtotal,
            'vat_amount': cn.vat_amount,
            'total': cn.total,
            'late_issuance': cn.late_issuance,
        }
        for cn in posted.order_by('issue_date', 'number')
    ]

    return supplies_reduction, vat_reduction, audit_rows
