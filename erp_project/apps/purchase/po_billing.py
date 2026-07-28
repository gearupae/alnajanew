"""
Partial vendor billing against PO lines — bill only received (unbilled) quantities.
"""
from decimal import Decimal

from django.db.models import Sum


def quantity_billed_for_po_item(po_item_id, *, exclude_bill_id=None):
    """Sum billed qty on draft/posted bills linked to this PO line."""
    from .models import VendorBillItem

    if not po_item_id:
        return Decimal('0.00')

    qs = VendorBillItem.objects.filter(
        purchase_order_item_id=po_item_id,
        bill__is_active=True,
    )

    if exclude_bill_id:
        qs = qs.exclude(bill_id=exclude_bill_id)

    total = qs.aggregate(s=Sum('quantity'))['s'] or Decimal('0')
    return total.quantize(Decimal('0.01'))


def quantity_billable_for_po_item(po_item, *, exclude_bill_id=None):
    """Received qty minus qty already on vendor bills."""
    received = po_item.quantity_received or Decimal('0')
    billed = quantity_billed_for_po_item(po_item.pk, exclude_bill_id=exclude_bill_id)
    billable = (received - billed).quantize(Decimal('0.01'))
    return max(Decimal('0.00'), billable)


def annotate_po_item_billing(po_item, *, exclude_bill_id=None):
    po_item.quantity_billed = quantity_billed_for_po_item(
        po_item.pk, exclude_bill_id=exclude_bill_id
    )
    po_item.quantity_billable = quantity_billable_for_po_item(
        po_item, exclude_bill_id=exclude_bill_id
    )
    return po_item


def po_has_received_items(po):
    return any((line.quantity_received or Decimal('0')) > 0 for line in po.items.all())


def po_has_billable_items(po, *, exclude_bill_id=None):
    """True when at least one PO line has received qty not yet on a vendor bill."""
    for line in po.items.all():
        if quantity_billable_for_po_item(line, exclude_bill_id=exclude_bill_id) > 0:
            return True
    return False


def vendor_bills_for_po(po):
    """All active vendor bills linked to this PO, newest first."""
    from .models import VendorBill

    return (
        VendorBill.objects.filter(purchase_order=po, is_active=True)
        .order_by('-bill_date', '-created_at', '-pk')
    )


def po_item_bill_allocations(po_item):
    """Bill lines posted against this PO item: [{bill, quantity}, ...]."""
    from .models import VendorBillItem

    rows = (
        VendorBillItem.objects.filter(
            purchase_order_item_id=po_item.pk,
            bill__is_active=True,
        )
        .select_related('bill')
        .order_by('bill__bill_date', 'bill__pk', 'pk')
    )
    return [
        {
            'bill': row.bill,
            'bill_id': row.bill_id,
            'bill_number': row.bill.bill_number,
            'bill_status': row.bill.status,
            'quantity': row.quantity,
        }
        for row in rows
    ]


def annotate_po_item_billing_details(po_item, *, exclude_bill_id=None):
    """Add quantity_billed, quantity_billable, and per-bill allocation list."""
    annotate_po_item_billing(po_item, exclude_bill_id=exclude_bill_id)
    po_item.bill_allocations = po_item_bill_allocations(po_item)
    return po_item


def _po_line_requires_whole_quantity(po_line):
    inv = getattr(po_line, 'inventory_item', None)
    return bool(inv and inv.requires_whole_quantity())


def po_items_billing_payload(po, *, bill_received_only=True, exclude_bill_id=None):
    """JSON-serializable PO lines for vendor bill form."""
    from apps.inventory.models import Item

    items = []
    any_billable = False
    for line in po.items.select_related('inventory_item').all().order_by('id'):
        annotate_po_item_billing(line, exclude_bill_id=exclude_bill_id)
        billable = line.quantity_billable
        whole_qty = _po_line_requires_whole_quantity(line)
        if whole_qty:
            billable = Item.normalize_quantity(line.inventory_item, billable)
        if bill_received_only:
            if billable <= 0:
                continue
            qty = billable
            any_billable = True
        else:
            qty = line.quantity or Decimal('0')
            if whole_qty:
                qty = Item.normalize_quantity(line.inventory_item, qty)

        items.append({
            'po_item_id': line.pk,
            'description': line.description,
            'quantity': str(qty),
            'quantity_ordered': str(line.quantity or Decimal('0')),
            'quantity_received': str(line.quantity_received or Decimal('0')),
            'quantity_billed': str(line.quantity_billed),
            'quantity_billable': str(billable),
            'unit_price': str(line.unit_price),
            'vat_rate': str(line.vat_rate),
            'tax_code_id': line.tax_code_id,
            'inventory_item_id': line.inventory_item_id,
            'requires_whole_quantity': whole_qty,
        })

    return {
        'items': items,
        'vendor_id': po.vendor_id,
        'project_id': po.project_id,
        'has_received_items': po_has_received_items(po),
        'any_billable': any_billable if bill_received_only else bool(items),
        'po_number': po.po_number,
        'po_status': po.status,
    }


def validate_vendor_bill_po_lines(bill, line_items, *, exclude_bill_id=None):
    """
    Validate bill line quantities against PO received/unbilled caps.
    Returns list of error strings (empty if valid).
    """
    from apps.inventory.models import Item
    from .models import PurchaseOrderItem

    errors = []
    po = bill.purchase_order
    if not po:
        return errors

    def _po_item_id(li):
        if hasattr(li, 'purchase_order_item_id'):
            return li.purchase_order_item_id
        val = li.get('purchase_order_item') if isinstance(li, dict) else None
        return getattr(val, 'pk', val) if val else None

    def _qty(li):
        if hasattr(li, 'quantity'):
            return li.quantity or Decimal('0')
        return li.get('quantity') or Decimal('0')

    def _desc(li):
        if hasattr(li, 'description'):
            return li.description
        return li.get('description') or ''

    po_item_ids = []
    for li in line_items:
        if isinstance(li, dict) and li.get('DELETE'):
            continue
        pid = _po_item_id(li)
        if pid:
            po_item_ids.append(pid)

    po_items_by_id = {
        row.pk: row
        for row in PurchaseOrderItem.objects.select_related('inventory_item').filter(
            pk__in=po_item_ids, purchase_order=po
        )
    }

    for li in line_items:
        if isinstance(li, dict) and li.get('DELETE'):
            continue
        po_item_id = _po_item_id(li)
        if not po_item_id:
            continue
        po_item = po_items_by_id.get(po_item_id)
        if not po_item:
            errors.append(f'Line "{_desc(li)}" is linked to an invalid PO item.')
            continue
        qty = _qty(li)
        if qty <= 0:
            continue
        inv = getattr(po_item, 'inventory_item', None)
        if inv and inv.requires_whole_quantity():
            if qty != qty.to_integral_value():
                errors.append(
                    f'"{po_item.description}": bill quantity must be a whole number.'
                )
                continue
            qty = Item.normalize_quantity(inv, qty)
        billable = quantity_billable_for_po_item(po_item, exclude_bill_id=exclude_bill_id)
        if inv and inv.requires_whole_quantity():
            billable = Item.normalize_quantity(inv, billable)
        if qty > billable:
            errors.append(
                f'"{po_item.description}": bill qty {qty} exceeds unbilled received qty {billable}.'
            )

    if bill.goods_received and not po_has_received_items(po):
        errors.append('Goods-received billing requires at least one received PO line.')

    if bill.goods_received and po.status not in ('partial_received', 'received'):
        errors.append(
            f'PO {po.po_number} must be partially or fully received before a GRN-matched bill.'
        )

    return errors


def bill_formset_lines_for_validation(items_formset):
    """Extract non-empty cleaned rows from a vendor bill item formset."""
    rows = []
    for form in items_formset.forms:
        if not form.cleaned_data:
            continue
        if form.cleaned_data.get('DELETE'):
            continue
        desc = (form.cleaned_data.get('description') or '').strip()
        unit_price = form.cleaned_data.get('unit_price')
        if not desc and not unit_price and unit_price != 0:
            continue
        rows.append(form.cleaned_data)
    return rows
