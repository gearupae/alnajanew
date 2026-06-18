"""Estimated (quotation) vs actual project expense breakdown for project detail."""
from __future__ import annotations

from decimal import Decimal


def build_project_expense_comparison_context(
    *,
    project,
    source_estimate,
    manual_expenses_total: Decimal,
    bills_total: Decimal,
    inventory_spend: Decimal,
    labour_cost: Decimal,
):
    """
    Estimated: expense-type totals from linked quotation(s) — qty × base price per line.
    Actual: labour timesheets, items delivered value, project expenses, vendor bills.
    """
    estimated_rows = []
    estimated_grand = Decimal('0.00')
    estimates = list(project.estimates.filter(is_active=True).order_by('date', 'pk'))
    if not estimates and source_estimate:
        estimates = [source_estimate]
    if estimates:
        from apps.sales.estimate_pdf_groups import build_expense_type_base_totals_for_estimates

        for row in build_expense_type_base_totals_for_estimates(estimates):
            estimated_rows.append({
                'label': row['expense_type_name'],
                'amount': row['line_total'],
            })
        if estimated_rows:
            estimated_grand = sum((r['amount'] for r in estimated_rows), Decimal('0.00'))

    actual_rows = [
        {'label': 'Labour (timesheets)', 'amount': labour_cost or Decimal('0.00')},
        {'label': 'Items delivered', 'amount': inventory_spend or Decimal('0.00')},
        {'label': 'Project expenses', 'amount': manual_expenses_total or Decimal('0.00')},
        {'label': 'Vendor bills', 'amount': bills_total or Decimal('0.00')},
    ]
    actual_grand = sum((r['amount'] for r in actual_rows), Decimal('0.00'))

    return {
        'estimated_expense_rows': estimated_rows,
        'estimated_expense_grand_total': estimated_grand,
        'actual_expense_rows': actual_rows,
        'actual_expense_grand_total': actual_grand,
        'show_expense_comparison_card': bool(estimates or actual_grand > 0),
    }
