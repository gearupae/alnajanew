"""
Consumables / inventory report data builders (JSON-friendly structures for UI + exports).
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

from dateutil.relativedelta import relativedelta
from django.db.models import (
    Case,
    Count,
    DecimalField,
    F,
    Q,
    Sum,
    Value,
    When,
)
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.inventory.models import Item, StockMovement
from apps.settings_app.models import CompanySettings


def signed_qty_case():
    return Case(
        When(movement_type='in', then=F('quantity')),
        When(movement_type='adjustment_plus', then=F('quantity')),
        When(movement_type='out', then=-F('quantity')),
        When(movement_type='adjustment_minus', then=-F('quantity')),
        When(movement_type='transfer', then=Value(Decimal('0'))),
        default=Value(Decimal('0')),
        output_field=DecimalField(max_digits=24, decimal_places=6),
    )


def _opening_map(date_from) -> dict[int, Decimal]:
    qs = (
        StockMovement.objects.filter(movement_date__lt=date_from, item__is_active=True, item__item_type='product')
        .values('item_id')
        .annotate(o=Coalesce(Sum(signed_qty_case()), Value(Decimal('0')), output_field=DecimalField(max_digits=24, decimal_places=6)))
    )
    return {r['item_id']: (r['o'] or Decimal('0')).quantize(Decimal('0.01')) for r in qs}


def _period_received_map(date_from, date_to) -> dict[int, Decimal]:
    qs = (
        StockMovement.objects.filter(
            movement_date__gte=date_from,
            movement_date__lte=date_to,
            movement_type__in=['in', 'adjustment_plus'],
            item__is_active=True,
            item__item_type='product',
        )
        .values('item_id')
        .annotate(r=Coalesce(Sum('quantity'), Value(Decimal('0')), output_field=DecimalField(max_digits=24, decimal_places=6)))
    )
    return {r['item_id']: (r['r'] or Decimal('0')).quantize(Decimal('0.01')) for r in qs}


def _period_issued_map(date_from, date_to) -> dict[int, Decimal]:
    qs = (
        StockMovement.objects.filter(
            movement_date__gte=date_from,
            movement_date__lte=date_to,
            movement_type__in=['out', 'adjustment_minus'],
            item__is_active=True,
            item__item_type='product',
        )
        .values('item_id')
        .annotate(r=Coalesce(Sum('quantity'), Value(Decimal('0')), output_field=DecimalField(max_digits=24, decimal_places=6)))
    )
    return {r['item_id']: (r['r'] or Decimal('0')).quantize(Decimal('0.01')) for r in qs}


def _unit_cost(item: Item) -> Decimal:
    if item.purchase_price and item.purchase_price > 0:
        return item.purchase_price.quantize(Decimal('0.01'))
    agg = StockMovement.objects.filter(item=item, movement_type='in', quantity__gt=0).aggregate(
        t=Sum('total_cost'), q=Sum('quantity')
    )
    t, q = agg['t'], agg['q']
    if t and q and q > 0:
        return (t / q).quantize(Decimal('0.01'))
    return Decimal('0.00')


def _stock_status(closing: Decimal, minimum: Decimal) -> tuple[str, str]:
    minimum = minimum or Decimal('0')
    if closing < minimum:
        return 'Low', 'danger'
    if minimum > 0 and closing > minimum * Decimal('3'):
        return 'Excess', 'warning'
    if minimum == 0 and closing > Decimal('500'):
        return 'Excess', 'warning'
    return 'OK', 'success'


def _item_base_qs():
    """Same scope as consumable dashboard / request forms: active stock items only."""
    return Item.objects.filter(
        is_active=True,
        item_type='product',
        status='active',
    ).select_related('category', 'storage_location_master')


def _attach_valuation_to_rows(rows: list[dict]) -> Decimal:
    """Add unit_cost and total_value (closing × unit cost) per row; return grand total."""
    item_ids = [r['item_id'] for r in rows if r.get('item_id')]
    items_by_id = {i.id: i for i in _item_base_qs().filter(pk__in=item_ids)}
    grand = Decimal('0')
    for r in rows:
        item = items_by_id.get(r.get('item_id'))
        uc = _unit_cost(item) if item else Decimal('0')
        closing = Decimal(str(r.get('closing', 0)))
        total_val = (closing * uc).quantize(Decimal('0.01'))
        r['unit_cost'] = float(uc)
        r['total_value'] = float(total_val)
        minimum = Decimal(str(r.get('minimum', 0) or 0))
        shortfall = (minimum - closing).quantize(Decimal('0.01'))
        r['shortfall'] = float(shortfall if shortfall > 0 else Decimal('0'))
        grand += total_val
    return grand.quantize(Decimal('0.01'))


LOW_STOCK_TABLE_COLUMNS = [
    {'key': 'item_code', 'label': 'Item Code', 'hint': 'ERP item code'},
    {'key': 'item_name', 'label': 'Item Name', 'hint': 'Product / consumable name'},
    {'key': 'category', 'label': 'Category', 'hint': 'Inventory category'},
    {'key': 'location', 'label': 'Storage Location', 'hint': 'Warehouse shelf or bin'},
    {'key': 'barcode', 'label': 'Barcode', 'hint': 'Barcode or asset tag'},
    {'key': 'unit', 'label': 'UoM', 'hint': 'Unit of measure (ea, box, kg, …)'},
    {'key': 'closing', 'label': 'Qty on Hand', 'format': 'number', 'hint': 'Quantity at end of selected period'},
    {'key': 'minimum', 'label': 'Min Stock', 'format': 'number', 'hint': 'Minimum stock level configured on item'},
    {'key': 'shortfall', 'label': 'Shortfall', 'format': 'number', 'hint': 'Qty needed to reach minimum (0 if OK)'},
    {'key': 'unit_cost', 'label': 'Unit Cost (AED)', 'format': 'money', 'hint': 'Purchase or weighted average cost'},
    {'key': 'total_value', 'label': 'Stock Value (AED)', 'format': 'money', 'hint': 'Qty on hand × unit cost'},
]


def _low_stock_rows_from_summary(rows: list[dict]) -> list[dict]:
    low = [r for r in rows if r.get('status') == 'Low']
    out = []
    for r in low:
        out.append(
            {
                'item_id': r.get('item_id'),
                'item_code': r.get('item_code', '') or '',
                'item_name': r['item_name'],
                'category': r.get('category', ''),
                'location': r.get('location', ''),
                'barcode': r.get('barcode', ''),
                'unit': r.get('unit', ''),
                'closing': r['closing'],
                'minimum': r['minimum'],
                'shortfall': r.get('shortfall', 0),
                'unit_cost': r.get('unit_cost', 0),
                'total_value': r.get('total_value', 0),
            }
        )
    return out


def _low_stock_table_payload(rows: list[dict], title: str = 'Low stock items') -> dict[str, Any]:
    low_rows = _low_stock_rows_from_summary(rows)
    low_grand = sum(Decimal(str(r.get('total_value', 0))) for r in low_rows).quantize(Decimal('0.01'))
    return {
        'title': title,
        'columns': LOW_STOCK_TABLE_COLUMNS,
        'rows': low_rows,
        'footer': {
            'grand_total_value': float(low_grand),
            'item_count': len(low_rows),
        },
    }


def report_stock_summary(date_from: date, date_to: date) -> dict[str, Any]:
    opening_m = _opening_map(date_from)
    recv_m = _period_received_map(date_from, date_to)
    iss_m = _period_issued_map(date_from, date_to)
    rows = []
    for item in _item_base_qs().order_by('name'):
        oid = item.id
        opening = opening_m.get(oid, Decimal('0'))
        received = recv_m.get(oid, Decimal('0'))
        issued = iss_m.get(oid, Decimal('0'))
        closing = (opening + received - issued).quantize(Decimal('0.01'))
        status, status_key = _stock_status(closing, item.minimum_stock)
        rows.append(
            {
                'item_id': item.id,
                'item_code': item.item_code,
                'item_name': item.name,
                'category': item.category.name if item.category_id else '',
                'unit': item.unit,
                'barcode': item.barcode or '',
                'location': item.get_storage_shelf_label(),
                'opening': float(opening),
                'received': float(received),
                'issued': float(issued),
                'closing': float(closing),
                'minimum': float(item.minimum_stock or 0),
                'status': status,
                'status_key': status_key,
            }
        )
    grand_total = _attach_valuation_to_rows(rows)
    return {
        'report': 'stock_summary',
        'title': 'Stock Summary Report',
        'description': 'Opening, movements, and closing quantity per active product for the selected date range. Values use purchase / average cost.',
        'columns': [
            {'key': 'item_code', 'label': 'Item Code', 'hint': 'ERP item code'},
            {'key': 'item_name', 'label': 'Item Name', 'hint': 'Product / consumable name'},
            {'key': 'category', 'label': 'Category', 'hint': 'Inventory category'},
            {'key': 'location', 'label': 'Storage Location', 'hint': 'Shelf, bin, or warehouse location'},
            {'key': 'barcode', 'label': 'Barcode', 'hint': 'Barcode or asset tag'},
            {'key': 'unit', 'label': 'UoM', 'hint': 'Unit of measure'},
            {'key': 'opening', 'label': 'Opening Qty', 'format': 'number', 'hint': 'Qty before period start date'},
            {'key': 'received', 'label': 'Received (+)', 'format': 'number', 'hint': 'Stock in during period (receipts, adjustments +)'},
            {'key': 'issued', 'label': 'Issued (−)', 'format': 'number', 'hint': 'Stock out during period (issues, adjustments −)'},
            {'key': 'closing', 'label': 'Closing Qty', 'format': 'number', 'hint': 'Qty on hand at period end'},
            {'key': 'minimum', 'label': 'Min Stock', 'format': 'number', 'hint': 'Configured minimum level'},
            {'key': 'unit_cost', 'label': 'Unit Cost (AED)', 'format': 'money', 'hint': 'Cost per unit'},
            {'key': 'total_value', 'label': 'Stock Value (AED)', 'format': 'money', 'hint': 'Closing qty × unit cost'},
            {'key': 'status', 'label': 'Stock Status', 'hint': 'Low, OK, or Excess vs minimum'},
        ],
        'rows': rows,
        'footer': {'grand_total_value': float(grand_total)},
        'low_stock_table': _low_stock_table_payload(rows),
    }


def report_low_stock(date_from: date, date_to: date) -> dict[str, Any]:
    summary = report_stock_summary(date_from, date_to)
    low_table = summary.get('low_stock_table') or _low_stock_table_payload(summary['rows'])
    return {
        'report': 'low_stock',
        'title': 'Low Stock Report',
        'description': 'Items below minimum stock for the period. Reorder using shortfall and value columns.',
        'columns': low_table['columns'],
        'rows': low_table['rows'],
        'footer': low_table.get('footer', {}),
    }


def report_stock_balance(date_from: date, date_to: date) -> dict[str, Any]:
    base = report_stock_summary(date_from, date_to)
    rows = []
    for r in base['rows']:
        rows.append(
            {
                'item_id': r['item_id'],
                'item_code': r.get('item_code', ''),
                'item_name': r['item_name'],
                'category': r['category'],
                'location': r['location'],
                'opening': r['opening'],
                'received': r['received'],
                'issued': r['issued'],
                'closing': r['closing'],
                'unit': r['unit'],
                'barcode': r['barcode'],
                'unit_cost': r.get('unit_cost', 0),
                'total_value': r.get('total_value', 0),
            }
        )
    return {
        'report': 'stock_balance',
        'title': 'Stock Balance Report',
        'description': 'Period movement summary: opening, total in/out, and closing balance per item.',
        'columns': [
            {'key': 'item_code', 'label': 'Item Code', 'hint': 'ERP item code'},
            {'key': 'item_name', 'label': 'Item Name', 'hint': 'Product name'},
            {'key': 'category', 'label': 'Category', 'hint': 'Inventory category'},
            {'key': 'location', 'label': 'Storage Location', 'hint': 'Shelf or warehouse location'},
            {'key': 'barcode', 'label': 'Barcode', 'hint': 'Barcode or asset tag'},
            {'key': 'opening', 'label': 'Opening Qty', 'format': 'number', 'hint': 'Balance at period start'},
            {'key': 'received', 'label': 'Total In (+)', 'format': 'number', 'hint': 'All receipts in period'},
            {'key': 'issued', 'label': 'Total Out (−)', 'format': 'number', 'hint': 'All issues in period'},
            {'key': 'closing', 'label': 'Closing Qty', 'format': 'number', 'hint': 'Balance at period end'},
            {'key': 'unit', 'label': 'UoM', 'hint': 'Unit of measure'},
            {'key': 'unit_cost', 'label': 'Unit Cost (AED)', 'format': 'money', 'hint': 'Cost per unit'},
            {'key': 'total_value', 'label': 'Stock Value (AED)', 'format': 'money', 'hint': 'Closing qty × unit cost'},
        ],
        'rows': rows,
        'footer': base.get('footer', {}),
        'low_stock_table': base.get('low_stock_table'),
    }


def report_inventory_valuation(date_from: date, date_to: date) -> dict[str, Any]:
    cs = CompanySettings.get_settings()
    method_label = cs.get_inventory_valuation_method_display()
    summary = report_stock_summary(date_from, date_to)
    rows = []
    grand = Decimal('0')
    for r in summary['rows']:
        item = Item.objects.filter(pk=r['item_id']).first()
        if not item:
            continue
        uc = _unit_cost(item)
        closing = Decimal(str(r['closing']))
        total_val = (closing * uc).quantize(Decimal('0.01'))
        grand += total_val
        rows.append(
            {
                'item_id': r['item_id'],
                'item_code': item.item_code,
                'item_name': r['item_name'],
                'category': r['category'],
                'unit': r['unit'],
                'barcode': r['barcode'],
                'location': r['location'],
                'qty': float(closing),
                'unit_cost': float(uc),
                'total_value': float(total_val),
                'last_updated': item.updated_at.date().isoformat() if item.updated_at else '',
            }
        )
    low_table = summary.get('low_stock_table') or _low_stock_table_payload(summary['rows'])
    return {
        'report': 'inventory_valuation',
        'title': 'Inventory Valuation Report',
        'description': f'Closing quantity valued using company method: {method_label}.',
        'valuation_method': method_label,
        'columns': [
            {'key': 'item_code', 'label': 'Item Code', 'hint': 'ERP item code'},
            {'key': 'item_name', 'label': 'Item Name', 'hint': 'Product name'},
            {'key': 'category', 'label': 'Category', 'hint': 'Inventory category'},
            {'key': 'location', 'label': 'Storage Location', 'hint': 'Shelf or warehouse location'},
            {'key': 'barcode', 'label': 'Barcode', 'hint': 'Barcode or asset tag'},
            {'key': 'unit', 'label': 'UoM', 'hint': 'Unit of measure'},
            {'key': 'qty', 'label': 'Qty on Hand', 'format': 'number', 'hint': 'Closing qty for the period'},
            {'key': 'unit_cost', 'label': 'Unit Cost (AED)', 'format': 'money', 'hint': 'Valuation cost per unit'},
            {'key': 'total_value', 'label': 'Total Value (AED)', 'format': 'money', 'hint': 'Qty × unit cost'},
            {'key': 'last_updated', 'label': 'Last Updated', 'format': 'date', 'hint': 'Item master last changed'},
        ],
        'rows': rows,
        'footer': {'grand_total_value': float(grand), 'valuation_method': method_label},
        'low_stock_table': low_table,
    }


def report_warranty(date_from: date, date_to: date, warranty_filter: str) -> dict[str, Any]:
    del date_from, date_to  # filter is snapshot-oriented; period still shown in header
    today = timezone.localdate()
    qs = _item_base_qs()
    rows = []
    for item in qs.order_by('name'):
        exp = item.warranty_expiry
        if not exp:
            if warranty_filter != 'all':
                continue
            rows.append(
                {
                    'item_code': item.item_code,
                    'item_name': item.name,
                    'brand': item.brand or '',
                    'serial_batch': item.serial_batch_number or '',
                    'purchase_date': item.purchase_date.isoformat() if item.purchase_date else '',
                    'warranty_expiry': '',
                    'days_remaining': '',
                    'status': 'N/A',
                    'status_key': 'secondary',
                    'barcode': item.barcode or '',
                    'location': item.get_storage_shelf_label(),
                }
            )
            continue
        days_left = (exp - today).days
        if days_left < 0:
            status, sk = 'Expired', 'danger'
        elif days_left < 30:
            status, sk = 'Expiring Soon', 'warning'
        else:
            status, sk = 'Active', 'success'
        if warranty_filter == 'expired' and status != 'Expired':
            continue
        if warranty_filter == 'expiring_soon' and status != 'Expiring Soon':
            continue
        rows.append(
            {
                'item_code': item.item_code,
                'item_name': item.name,
                'brand': item.brand or '',
                'serial_batch': item.serial_batch_number or '',
                'purchase_date': item.purchase_date.isoformat() if item.purchase_date else '',
                'warranty_expiry': exp.isoformat(),
                'days_remaining': days_left,
                'status': status,
                'status_key': sk,
                'barcode': item.barcode or '',
                'location': item.get_storage_shelf_label(),
            }
        )
    return {
        'report': 'warranty',
        'title': 'Warranty Period Report',
        'description': 'Warranty status snapshot (not limited by date range). Use the warranty filter for expired / expiring items.',
        'columns': [
            {'key': 'item_code', 'label': 'Item Code', 'hint': 'ERP item code'},
            {'key': 'item_name', 'label': 'Item Name', 'hint': 'Product name'},
            {'key': 'brand', 'label': 'Brand', 'hint': 'Manufacturer or brand'},
            {'key': 'location', 'label': 'Storage Location', 'hint': 'Current storage location'},
            {'key': 'barcode', 'label': 'Barcode', 'hint': 'Barcode or asset tag'},
            {'key': 'serial_batch', 'label': 'Serial / Batch', 'hint': 'Serial or batch number'},
            {'key': 'purchase_date', 'label': 'Purchase Date', 'format': 'date', 'hint': 'Date item was purchased'},
            {'key': 'warranty_expiry', 'label': 'Warranty End', 'format': 'date', 'hint': 'Warranty expiry date'},
            {'key': 'days_remaining', 'label': 'Days Left', 'format': 'number', 'hint': 'Days until expiry (negative if expired)'},
            {'key': 'status', 'label': 'Warranty Status', 'hint': 'Active, Expiring Soon, Expired, or N/A'},
        ],
        'rows': rows,
    }


def _movement_type_label(m: StockMovement) -> str:
    if m.movement_type == 'in':
        return 'Returned' if m.source == 'return' else 'Received'
    if m.movement_type == 'out':
        return 'Issued'
    if m.movement_type == 'adjustment_plus':
        return 'Adjusted (+)'
    if m.movement_type == 'adjustment_minus':
        return 'Adjusted (-)'
    if m.movement_type == 'transfer':
        return 'Transfer'
    return m.get_movement_type_display()


def report_stock_movement(date_from: date, date_to: date, group_by: str) -> dict[str, Any]:
    qs = (
        StockMovement.objects.filter(
            movement_date__gte=date_from,
            movement_date__lte=date_to,
            item__is_active=True,
            item__item_type='product',
        )
        .select_related('item', 'item__category', 'item__storage_location_master', 'created_by')
        .order_by('movement_date', 'id')
    )
    raw_rows = []
    for m in qs:
        user = m.created_by
        moved_by = user.get_full_name().strip() if user and user.get_full_name() else (user.username if user else '')
        raw_rows.append(
            {
                'date': m.movement_date.isoformat(),
                'item_code': m.item.item_code,
                'item_name': m.item.name,
                'barcode': m.item.barcode or '',
                'location': m.item.get_storage_shelf_label(),
                'type': _movement_type_label(m),
                'quantity': float(abs(m.quantity)),
                'reference': m.reference or '',
                'moved_by': moved_by,
                'remarks': m.notes or '',
            }
        )
    rows = raw_rows
    if group_by == 'item':
        buckets: dict[str, list] = defaultdict(list)
        for r in raw_rows:
            buckets[r['item_name']].append(r)
        rows = []
        for item_name in sorted(buckets.keys()):
            for r in buckets[item_name]:
                rows.append(r)
    elif group_by == 'date':
        buckets = defaultdict(list)
        for r in raw_rows:
            buckets[r['date']].append(r)
        rows = []
        for d in sorted(buckets.keys()):
            for r in buckets[d]:
                rows.append(r)
    return {
        'report': 'stock_movement',
        'title': 'Stock Movement Report',
        'description': 'Every stock movement in the date range. Group by date or item using the toolbar filter.',
        'columns': [
            {'key': 'date', 'label': 'Movement Date', 'format': 'date', 'hint': 'Posting date of movement'},
            {'key': 'item_code', 'label': 'Item Code', 'hint': 'ERP item code'},
            {'key': 'item_name', 'label': 'Item Name', 'hint': 'Product name'},
            {'key': 'location', 'label': 'Storage Location', 'hint': 'Item storage location'},
            {'key': 'barcode', 'label': 'Barcode', 'hint': 'Barcode or asset tag'},
            {'key': 'type', 'label': 'Movement Type', 'hint': 'Received, Issued, Transfer, Adjustment, …', 'badge': True},
            {'key': 'quantity', 'label': 'Qty', 'format': 'number', 'hint': 'Absolute quantity moved'},
            {'key': 'reference', 'label': 'Reference', 'hint': 'Linked document (GRN, issue, etc.)'},
            {'key': 'moved_by', 'label': 'Recorded By', 'hint': 'User who posted the movement'},
            {'key': 'remarks', 'label': 'Notes', 'hint': 'Movement notes'},
        ],
        'rows': rows,
    }


def report_inventory_analytics(date_from: date, date_to: date) -> dict[str, Any]:
    summary = report_stock_summary(date_from, date_to)
    low = ok = excess = 0
    total_value = Decimal('0')
    total_issued = Decimal('0')
    closing_sum = Decimal('0')
    items_by_id = {i.id: i for i in _item_base_qs()}
    for r in summary['rows']:
        if r['status'] == 'Low':
            low += 1
        elif r['status'] == 'Excess':
            excess += 1
        else:
            ok += 1
        item = items_by_id.get(r['item_id'])
        if item:
            uc = _unit_cost(item)
            c = Decimal(str(r['closing']))
            total_value += c * uc
            closing_sum += c
        total_issued += Decimal(str(r['issued']))

    # Monthly consumption trend (12 months ending month of date_to)
    monthly_labels = []
    monthly_qty = []
    end_month = date(date_to.year, date_to.month, 1)
    for i in range(11, -1, -1):
        ms = end_month - relativedelta(months=i)
        me = ms + relativedelta(months=1)
        q = StockMovement.objects.filter(
            movement_type='out',
            movement_date__gte=ms,
            movement_date__lt=me,
            item__item_type='product',
            item__is_active=True,
        ).aggregate(t=Coalesce(Sum('quantity'), Value(Decimal('0'))))['t'] or Decimal('0')
        monthly_labels.append(ms.strftime('%b %Y'))
        monthly_qty.append(float(q))

    # Top 10 consumed (out qty) in selected period
    top = (
        StockMovement.objects.filter(
            movement_type='out',
            movement_date__gte=date_from,
            movement_date__lte=date_to,
            item__is_active=True,
            item__item_type='product',
        )
        .values('item__name')
        .annotate(tq=Sum('quantity'))
        .order_by('-tq')[:10]
    )
    top_labels = [t['item__name'] for t in top]
    top_data = [float(t['tq'] or 0) for t in top]

    avg_turn = float(total_issued / (closing_sum or Decimal('1')))

    return {
        'report': 'inventory_analytics',
        'title': 'Inventory Analytics Report',
        'description': 'KPIs, charts, and stock health for active products in the selected period.',
        'kpi': {
            'total_items': len(summary['rows']),
            'total_value': float(total_value.quantize(Decimal('0.01'))),
            'low_stock_count': low,
            'avg_turnover_rate': round(avg_turn, 4),
        },
        'charts': {
            'monthly_labels': monthly_labels,
            'monthly_qty': monthly_qty,
            'pie': {'labels': ['Low', 'OK', 'Excess'], 'data': [low, ok, excess]},
            'top_labels': top_labels,
            'top_data': top_data,
        },
        'columns': [
            {'key': 'item_code', 'label': 'Item Code', 'hint': 'ERP item code'},
            {'key': 'item_name', 'label': 'Item Name', 'hint': 'Product name'},
            {'key': 'category', 'label': 'Category', 'hint': 'Inventory category'},
            {'key': 'location', 'label': 'Storage Location', 'hint': 'Shelf or warehouse'},
            {'key': 'barcode', 'label': 'Barcode', 'hint': 'Barcode or asset tag'},
            {'key': 'closing', 'label': 'Closing Qty', 'format': 'number', 'hint': 'Qty on hand at period end'},
            {'key': 'status', 'label': 'Stock Status', 'hint': 'Low, OK, or Excess'},
        ],
        'rows': [
            {
                'item_id': r['item_id'],
                'item_code': r.get('item_code', ''),
                'item_name': r['item_name'],
                'category': r['category'],
                'location': r['location'],
                'barcode': r['barcode'],
                'closing': r['closing'],
                'status': r['status'],
                'status_key': r['status_key'],
            }
            for r in summary['rows']
        ],
    }


REPORT_BUILDERS = {
    'stock_summary': report_stock_summary,
    'low_stock': report_low_stock,
    'inventory_analytics': report_inventory_analytics,
    'inventory_valuation': report_inventory_valuation,
    'warranty': report_warranty,
    'stock_movement': report_stock_movement,
    'stock_balance': report_stock_balance,
}


def build_report(
    report_key: str,
    date_from: date,
    date_to: date,
    warranty_filter: str = 'all',
    movement_group: str = 'date',
) -> dict[str, Any]:
    if report_key == 'warranty':
        return REPORT_BUILDERS[report_key](date_from, date_to, warranty_filter)
    if report_key == 'stock_movement':
        return REPORT_BUILDERS[report_key](date_from, date_to, movement_group)
    return REPORT_BUILDERS[report_key](date_from, date_to)
