"""VAT return helpers for posted purchase debit notes."""
from decimal import Decimal

from django.db.models import Sum

from .models import DebitNote, DebitNoteLine


def debit_note_period_adjustments(period_start, period_end):
    """
    Return (expense_reduction, vat_reduction, audit_rows) for posted debit notes
    in the vendor credit note date period.
    """
    posted = DebitNote.objects.filter(
        is_active=True,
        status='posted',
        vendor_credit_note_date__gte=period_start,
        vendor_credit_note_date__lte=period_end,
    ).select_related('vendor', 'original_bill')

    lines = DebitNoteLine.objects.filter(
        debit_note__in=posted,
        vat_rate__gt=0,
    )

    expense_reduction = lines.aggregate(total=Sum('line_total'))['total'] or Decimal('0.00')
    vat_reduction = lines.aggregate(total=Sum('line_vat'))['total'] or Decimal('0.00')

    audit_rows = [
        {
            'number': dn.number,
            'vendor_name': dn.vendor.name,
            'vendor_cn_ref': dn.vendor_credit_note_ref,
            'vendor_cn_date': dn.vendor_credit_note_date,
            'original_bill': dn.original_bill.bill_number,
            'subtotal': dn.subtotal,
            'vat_amount': dn.vat_amount,
            'total': dn.total,
        }
        for dn in posted.order_by('vendor_credit_note_date', 'number')
    ]

    return expense_reduction, vat_reduction, audit_rows
