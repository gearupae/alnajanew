"""Group line items for estimate PDF rendering."""
from __future__ import annotations

from decimal import Decimal


def _itemgroup_hide_by_name():
    from apps.inventory.models import ItemGroup

    return {
        (g.name or '').strip().lower(): g.hide_items_on_pdf
        for g in ItemGroup.objects.all()
    }


def _itemgroup_expense_type_by_name():
    from apps.inventory.models import ItemGroup

    result = {}
    for g in ItemGroup.objects.select_related('expense_type').filter(expense_type__isnull=False):
        key = (g.name or '').strip().lower()
        if not key or not g.expense_type_id:
            continue
        result[key] = {
            'expense_type_name': g.expense_type.name,
            'expense_type_sort_order': g.expense_type.sort_order,
        }
    return result


def build_expense_type_totals(item_groups):
    """
    Totals by expense type (incl. VAT) for estimate sections whose inventory
    sub-group has an expense type assigned. item_groups: build_pdf_item_groups.
    """
    expense_by_name = _itemgroup_expense_type_by_name()
    by_type = {}
    for grp in item_groups:
        name = (grp.get('name') or '').strip()
        if not name:
            continue
        meta = expense_by_name.get(name.lower())
        if not meta:
            continue
        type_name = meta['expense_type_name']
        entry = by_type.setdefault(type_name, {
            'expense_type_name': type_name,
            'expense_type_sort_order': meta['expense_type_sort_order'],
            'line_total': Decimal('0.00'),
        })
        entry['line_total'] += grp.get('line_total') or Decimal('0.00')

    totals = list(by_type.values())
    totals.sort(key=lambda row: (row['expense_type_sort_order'], row['expense_type_name']))
    return totals


def _effective_group_names(items) -> list[str]:
    """
    Resolve group_name per line in document order.
    Blank group_name inherits the previous non-empty group (common when a new
    line is added without re-entering the section name).
    """
    prev = ''
    names: list[str] = []
    for item in items:
        name = (getattr(item, 'group_name', None) or '').strip()
        if not name and prev:
            name = prev
        elif name:
            prev = name
        names.append(name)
    return names


def _line_amount(item) -> Decimal:
    return (getattr(item, 'total', None) or Decimal('0.00')) + (
        getattr(item, 'vat_amount', None) or Decimal('0.00')
    )


def _build_consecutive_groups(items, hide_by_name: dict, *, apply_hide_items: bool = True) -> list[dict]:
    """
    Build PDF sections from consecutive lines sharing the same effective group
    name (preserves estimate sort order; subtotal follows each run).
    """
    if not items:
        return []

    names = _effective_group_names(items)
    groups: list[dict] = []
    row_index = 0
    idx = 0

    while idx < len(items):
        name = names[idx]
        chunk: list = []
        line_total = Decimal('0.00')
        line_subtotal = Decimal('0.00')

        while idx < len(items) and names[idx] == name:
            item = items[idx]
            chunk.append(item)
            line_total += _line_amount(item)
            line_subtotal += getattr(item, 'total', None) or Decimal('0.00')
            idx += 1

        hide_items = (
            bool(name and hide_by_name.get(name.lower(), False))
            if apply_hide_items
            else False
        )
        numbered_items = []
        if not hide_items:
            for item in chunk:
                row_index += 1
                numbered_items.append({'item': item, 'index': row_index})

        groups.append({
            'name': name,
            'items': numbered_items,
            'line_total': line_total,
            'line_subtotal': line_subtotal,
            'hide_items_on_pdf': hide_items,
        })

    return groups


def build_pdf_item_groups(estimate):
    """
    Ordered groups of estimate lines for PDF.
    Consecutive lines with the same group name form one section (in sort_order).
    Each entry: name, items, line_total, line_subtotal, hide_items_on_pdf.
    line_total is incl. VAT per line.
    """
    hide_by_name = _itemgroup_hide_by_name()
    items = list(
        estimate.items.select_related('inventory_item').order_by('sort_order', 'id')
    )
    return _build_consecutive_groups(items, hide_by_name, apply_hide_items=True)


def build_item_groups_for_estimate_detail(estimate):
    """
    Item grouping for the *on-screen* estimate detail page.
    It must show all items even when `hide_items_on_pdf` is enabled for an
    inventory sub-group (that setting is for PDFs only).
    """
    items = list(estimate.items.select_related('inventory_item').order_by('sort_order', 'id'))
    # No need to query ItemGroup.hide_items_on_pdf for the on-screen view.
    return _build_consecutive_groups(items, {}, apply_hide_items=False)


def build_pdf_item_groups_for_line_items(line_items):
    """Same grouping as build_pdf_item_groups, for snapshot / mock line rows."""
    hide_by_name = _itemgroup_hide_by_name()
    items = list(line_items)
    return _build_consecutive_groups(items, hide_by_name, apply_hide_items=True)
