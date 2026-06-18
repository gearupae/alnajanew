"""Detect whether an estimate edit form actually changed data."""
from decimal import Decimal, InvalidOperation

# Header fields that change subtotal / discount / VAT / grand total.
AMOUNT_HEADER_FIELDS = frozenset({'discount_type', 'discount_value'})

# Line fields that change line net, VAT, or grand total (excludes description / group label).
AMOUNT_ITEM_FIELDS = frozenset({
    'quantity',
    'unit_price',
    'profit_type',
    'profit_value',
    'rate',
    'tax_code',
    'is_vat_inclusive',
    'inventory_item',
})


def _normalize_decimal(val) -> str:
    if val is None or val == '':
        return '0.00'
    try:
        return str(Decimal(str(val)).quantize(Decimal('0.01')))
    except (InvalidOperation, ValueError, TypeError):
        return str(val)


def capture_estimate_pricing_snapshot(estimate) -> dict:
    """
    Pricing fingerprint from persisted estimate + lines (discount and line amounts only).
    Used after save to decide whether a revision bump is warranted.
    """
    return {
        'discount_type': estimate.discount_type or '',
        'discount_value': _normalize_decimal(estimate.discount_value),
        'lines': tuple(
            (
                _normalize_decimal(row['quantity']),
                _normalize_decimal(row['unit_price']),
                row['profit_type'] or '',
                _normalize_decimal(row['profit_value']),
                row['tax_code_id'],
                row['inventory_item_id'],
                bool(row['is_vat_inclusive']),
            )
            for row in estimate.items.order_by('sort_order', 'id').values(
                'quantity',
                'unit_price',
                'profit_type',
                'profit_value',
                'tax_code_id',
                'inventory_item_id',
                'is_vat_inclusive',
            )
        ),
    }


def estimate_pricing_snapshots_differ(before: dict, after: dict) -> bool:
    return before != after


def _item_form_has_pricing_content(cleaned_data) -> bool:
    if not cleaned_data:
        return False
    desc = (cleaned_data.get('description') or '').strip()
    inv = cleaned_data.get('inventory_item')
    unit_price = cleaned_data.get('unit_price')
    try:
        price = Decimal(str(unit_price or '0'))
    except Exception:
        price = Decimal('0')
    qty = cleaned_data.get('quantity')
    try:
        quantity = Decimal(str(qty or '0'))
    except Exception:
        quantity = Decimal('0')
    return bool(inv or desc or price > 0 or quantity > 0)


def estimate_form_has_changes(form, items_formset) -> bool:
    """True when header or line items were modified (not a no-op save)."""
    if form.has_changed():
        return True
    if items_formset.has_changed():
        return True
    return False


def estimate_form_has_amount_affecting_changes(form, items_formset) -> bool:
    """
    True when discount or line pricing changed — i.e. anything that would
    change the amount section (subtotal, discount, VAT, total).
    """
    if form.has_changed() and AMOUNT_HEADER_FIELDS.intersection(form.changed_data):
        return True

    for item_form in items_formset.forms:
        if not hasattr(item_form, 'cleaned_data') or not item_form.cleaned_data:
            continue
        if item_form.cleaned_data.get('DELETE'):
            return True
        if not item_form.instance.pk and _item_form_has_pricing_content(item_form.cleaned_data):
            return True
        if item_form.has_changed() and AMOUNT_ITEM_FIELDS.intersection(item_form.changed_data):
            return True

    return False
