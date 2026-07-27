"""Customer receipts (invoices + advances) for project financial columns."""
from __future__ import annotations

from decimal import Decimal

from django.db.models import Sum

from apps.advances.models import CustomerAdvance, CustomerAdvanceApplication

def _linked_invoices_for_project(project):
    rows = []
    for link in project.invoices.filter(is_active=True).select_related('invoice'):
        inv = link.invoice
        if not inv or not inv.is_active or inv.status in ('draft', 'cancelled'):
            continue
        rows.append(inv)
    return rows


def project_receipt_totals(project) -> dict:
    """
    Cash received from the customer for this project.

    Includes posted customer advances (total incl. VAT) plus invoice payments,
    without double-counting advance amounts already applied to linked invoices.
    """
    invoices = _linked_invoices_for_project(project)
    invoice_ids = [inv.pk for inv in invoices]

    invoiced = sum((inv.total_amount or Decimal('0.00') for inv in invoices), Decimal('0.00'))
    invoice_paid = sum((inv.paid_amount or Decimal('0.00') for inv in invoices), Decimal('0.00'))

    advance_received = CustomerAdvance.objects.filter(
        project=project,
        is_active=True,
        status='posted',
    ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')

    advance_applied = Decimal('0.00')
    if invoice_ids:
        advance_applied = CustomerAdvanceApplication.objects.filter(
            advance__project=project,
            advance__is_active=True,
            invoice_id__in=invoice_ids,
            is_active=True,
        ).aggregate(total=Sum('amount_applied'))['total'] or Decimal('0.00')

    received = (advance_received + invoice_paid - advance_applied).quantize(Decimal('0.01'))
    contract = project.contract_value or Decimal('0.00')
    if contract > 0:
        balance = (contract - received).quantize(Decimal('0.01'))
    else:
        balance = (invoiced - received).quantize(Decimal('0.01'))

    return {
        'invoiced_amount': invoiced.quantize(Decimal('0.01')),
        'received_amount': received,
        'advance_received': advance_received.quantize(Decimal('0.01')),
        'invoice_paid': invoice_paid.quantize(Decimal('0.01')),
        'balance_amount': balance,
    }
