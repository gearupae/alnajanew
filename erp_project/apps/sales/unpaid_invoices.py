"""Unpaid / outstanding sales invoice helpers and CSV export."""
from __future__ import annotations

import csv
from datetime import date

from django.db.models import F
from django.http import HttpResponse

from .models import Invoice


def unpaid_invoices_queryset(base=None):
    """Active invoices with an outstanding balance (excludes draft and cancelled)."""
    qs = base if base is not None else Invoice.objects.filter(is_active=True)
    return (
        qs.select_related('customer')
        .exclude(status__in=['draft', 'cancelled'])
        .filter(total_amount__gt=F('paid_amount'))
        .order_by('due_date', 'invoice_number')
    )


def customer_display_name(invoice) -> str:
    customer = invoice.customer
    if not customer:
        return ''
    return (customer.company or customer.name or '').strip()


def invoices_csv_response(queryset, *, filename: str | None = None) -> HttpResponse:
    """Download invoice rows as CSV."""
    filename = filename or f'invoices_{date.today().isoformat()}.csv'
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response.write('\ufeff')
    writer = csv.writer(response)
    writer.writerow([
        'Invoice number',
        'Customer',
        'Invoice date',
        'Due date',
        'Status',
        'Total (AED)',
        'Paid (AED)',
        'Balance (AED)',
    ])
    for inv in queryset:
        writer.writerow([
            inv.invoice_number,
            customer_display_name(inv),
            inv.invoice_date.isoformat() if inv.invoice_date else '',
            inv.due_date.isoformat() if inv.due_date else '',
            inv.get_status_display(),
            f'{inv.total_amount:.2f}',
            f'{inv.paid_amount:.2f}',
            f'{inv.balance:.2f}',
        ])
    return response
