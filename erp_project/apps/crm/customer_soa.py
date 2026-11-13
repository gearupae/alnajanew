"""Customer Statement of Account (SOA) — open invoices, projects, estimates."""
from __future__ import annotations

from decimal import Decimal

from apps.core.visibility import filter_estimates_for_user, filter_projects_for_user
from apps.sales.models import Estimate, Invoice
from apps.sales.unpaid_invoices import unpaid_invoices_queryset


def build_customer_soa(customer, user):
    """
    Build statement rows and totals for one customer.
    Open invoices: non-draft/cancelled with balance > 0 (includes sent, partial, overdue, etc.).
    """
    open_qs = unpaid_invoices_queryset(
        Invoice.objects.filter(customer=customer).select_related(
            'estimate',
            'estimate__project',
        )
    )
    open_invoices = list(open_qs)

    outstanding = Decimal('0.00')
    invoiced_open = Decimal('0.00')
    paid_open = Decimal('0.00')
    for inv in open_invoices:
        outstanding += inv.balance
        invoiced_open += inv.total_amount or Decimal('0.00')
        paid_open += inv.paid_amount or Decimal('0.00')

    projects_qs = filter_projects_for_user(
        customer.projects.filter(is_active=True).order_by('-created_at', '-pk'),
        user,
    )
    project_rows = []
    try:
        from apps.projects.project_receipt_metrics import project_receipt_totals
    except ImportError:
        project_receipt_totals = None

    for project in projects_qs:
        receipt = project_receipt_totals(project) if project_receipt_totals else {}
        project_rows.append(
            {
                'project': project,
                'contract_value': project.contract_value or Decimal('0.00'),
                'invoiced_amount': receipt.get('invoiced_amount', Decimal('0.00')),
                'received_amount': receipt.get('received_amount', Decimal('0.00')),
                'balance_amount': receipt.get('balance_amount', Decimal('0.00')),
            }
        )

    estimates_qs = filter_estimates_for_user(
        Estimate.objects.filter(customer=customer, is_active=True)
        .select_related('project')
        .order_by('-date', '-pk'),
        user,
    )
    estimate_rows = list(estimates_qs)

    estimate_total = sum(
        (e.total_amount or Decimal('0.00') for e in estimate_rows),
        Decimal('0.00'),
    ).quantize(Decimal('0.01'))

    return {
        'soa_open_invoices': open_invoices,
        'soa_summary': {
            'open_invoice_count': len(open_invoices),
            'outstanding': outstanding.quantize(Decimal('0.01')),
            'invoiced_open': invoiced_open.quantize(Decimal('0.01')),
            'paid_open': paid_open.quantize(Decimal('0.01')),
            'estimate_count': len(estimate_rows),
            'estimate_total': estimate_total,
            'project_count': len(project_rows),
        },
        'soa_projects': project_rows,
        'soa_estimates': estimate_rows,
    }
