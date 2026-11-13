"""Vendor Statement of Account (SOA) — open bills and pending payables."""
from __future__ import annotations

from decimal import Decimal

from django.db.models import F

from apps.advances.models import VendorAdvance
from apps.purchase.models import VendorBill


def unpaid_vendor_bills_queryset(vendor, base=None):
    """Posted bills with outstanding balance (excludes draft)."""
    qs = base if base is not None else VendorBill.objects.filter(
        vendor=vendor,
        is_active=True,
    )
    return (
        qs.select_related('project', 'purchase_order')
        .exclude(status='draft')
        .filter(total_amount__gt=F('paid_amount'))
        .order_by('due_date', 'bill_number')
    )


def build_vendor_soa(vendor):
    open_bills = list(unpaid_vendor_bills_queryset(vendor))

    outstanding = Decimal('0.00')
    billed_open = Decimal('0.00')
    paid_open = Decimal('0.00')
    for bill in open_bills:
        outstanding += bill.balance
        billed_open += bill.total_amount or Decimal('0.00')
        paid_open += bill.paid_amount or Decimal('0.00')

    advance_rows = list(
        VendorAdvance.objects.filter(
            vendor=vendor,
            is_active=True,
            status='posted',
        )
        .filter(amount__gt=F('applied_amount'))
        .order_by('-date', '-pk')
    )
    advance_balance = sum(
        (adv.balance for adv in advance_rows),
        Decimal('0.00'),
    ).quantize(Decimal('0.01'))

    outstanding = outstanding.quantize(Decimal('0.01'))
    net_payable = (outstanding - advance_balance).quantize(Decimal('0.01'))

    return {
        'soa_open_bills': open_bills,
        'soa_advance_rows': advance_rows,
        'soa_summary': {
            'open_bill_count': len(open_bills),
            'outstanding': outstanding,
            'billed_open': billed_open.quantize(Decimal('0.01')),
            'paid_open': paid_open.quantize(Decimal('0.01')),
            'advance_balance': advance_balance,
            'net_payable': net_payable,
            'advance_count': len(advance_rows),
        },
    }
