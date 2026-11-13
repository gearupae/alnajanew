"""Bill remaining project / quotation balance on new sales invoices."""
from __future__ import annotations

from decimal import Decimal

from apps.projects.project_receipt_metrics import _linked_invoices_for_project
from apps.sales.vat_pricing import line_uses_inclusive_pricing


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(Decimal('0.01'))


def project_invoiced_total(project, *, include_drafts: bool = True) -> Decimal:
    """Sum of linked invoice totals (non-cancelled)."""
    invoices = _linked_invoices_for_project(project, include_drafts=include_drafts)
    return _quantize(
        sum((inv.total_amount or Decimal('0.00') for inv in invoices), Decimal('0.00'))
    )


def project_billing_caps(project, estimate=None) -> dict:
    """
    Contract / quotation cap minus amounts already on linked invoices.
    """
    billed = project_invoiced_total(project)
    cap = project.contract_value or Decimal('0.00')
    if estimate is not None:
        estimate.calculate_totals()
        est_total = estimate.total_amount or Decimal('0.00')
        if est_total > cap:
            cap = est_total
    if cap <= 0 and estimate is not None:
        cap = estimate.total_amount or Decimal('0.00')
    remaining = max(cap - billed, Decimal('0.00'))
    return {
        'contract_cap': _quantize(cap),
        'invoiced_total': billed,
        'remaining_to_bill': _quantize(remaining),
    }


def build_invoice_prefill_from_estimate(estimate, project, *, include_drafts: bool = True) -> list[dict]:
    """
    Line-item dicts for InvoiceItemFormSet initial, scaled to unbilled project balance.
    """
    caps = project_billing_caps(project, estimate)
    remaining = caps['remaining_to_bill']
    if remaining <= 0:
        return []

    estimate.calculate_totals()
    items = list(estimate.items.select_related('tax_code').order_by('sort_order', 'id'))
    if not items:
        return [
            {
                'description': f'Project {project.project_code} — balance billing',
                'quantity': Decimal('1'),
                'unit_price': remaining,
                'tax_code': None,
            }
        ]

    est_total = estimate.total_amount or Decimal('0.00')
    scale = Decimal('1')
    if est_total > 0 and remaining < est_total:
        scale = remaining / est_total

    line_amounts, _, _discount_amt = estimate.discounted_line_amounts(items)
    rows = []
    for item, (line_net, line_vat) in zip(items, line_amounts):
        line_net = (line_net * scale).quantize(Decimal('0.01'))
        line_vat = (line_vat * scale).quantize(Decimal('0.01'))
        qty = item.quantity or Decimal('1')
        if qty <= 0:
            qty = Decimal('1')
        inclusive = line_uses_inclusive_pricing(item)
        if inclusive:
            line_gross = (line_net + line_vat).quantize(Decimal('0.01'))
            unit_price = (line_gross / qty).quantize(Decimal('0.01'))
        else:
            unit_price = (line_net / qty).quantize(Decimal('0.01'))
        desc = (item.description or '').strip() or (item.inventory_item.name if item.inventory_item_id else 'Line')
        rows.append(
            {
                'description': desc,
                'quantity': qty,
                'unit_price': unit_price,
                'tax_code': item.tax_code_id,
                'is_vat_inclusive': inclusive,
                'inventory_item': item.inventory_item_id,
            }
        )
    return rows
