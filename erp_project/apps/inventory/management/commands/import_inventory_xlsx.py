"""
Import inventory items from Zoho-style Excel export.

Expected columns: Type, Item Code, Name, Cost Price, Average Cost Price,
Sales Price, Available, Unit, Stock Alert

Usage:
    python manage.py import_inventory_xlsx --file inventory.xlsx
    python manage.py import_inventory_xlsx --file inventory.xlsx --replace-all
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

import openpyxl
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from apps.finance.models import TaxCode
from apps.inventory.models import Item, Stock, Warehouse

EXPECTED_COLUMNS = [
    'Type',
    'Item Code',
    'Name',
    'Cost Price',
    'Average Cost Price',
    'Sales Price',
    'Available',
    'Unit',
    'Stock Alert',
]


def _is_blank(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    try:
        import math
        if isinstance(value, float) and math.isnan(value):
            return True
    except TypeError:
        pass
    return False


def _cell_str(value) -> str:
    if _is_blank(value):
        return ''
    return str(value).strip()


def _parse_decimal(value) -> Decimal:
    if _is_blank(value):
        return Decimal('0.00')
    try:
        return Decimal(str(value)).quantize(Decimal('0.01'))
    except (InvalidOperation, ValueError):
        return Decimal('0.00')


def _parse_item_code(value) -> str:
    if _is_blank(value):
        return ''
    if isinstance(value, float):
        return str(int(value))
    text = _cell_str(value)
    if text.endswith('.0'):
        text = text[:-2]
    return text[:50]


def _normalize_unit(raw: str) -> str:
    unit = _cell_str(raw).lower().replace("'", '')
    mapping = {
        'no': 'pcs',
        'nos': 'pcs',
        'ea': 'pcs',
        'each': 'pcs',
        'meter': 'm',
        'metre': 'm',
        'length': 'length',
        'lot': 'lot',
        'box': 'box',
        'pkt': 'pkt',
        'doz': 'doz',
        'kg': 'kg',
        'units': 'units',
        'pcs': 'pcs',
    }
    return mapping.get(unit, unit or 'pcs')[:20]


def _parse_item_type(raw: str) -> str:
    value = _cell_str(raw).lower()
    if value == 'service':
        return 'service'
    return 'product'


def _purchase_price(row: dict) -> Decimal:
    cost = _parse_decimal(row.get('Cost Price'))
    if cost > 0:
        return cost
    return _parse_decimal(row.get('Average Cost Price'))


def _detect_header_row(rows: list[tuple]) -> int:
    for idx, row in enumerate(rows[:5]):
        headers = {_cell_str(v) for v in row if _cell_str(v)}
        if 'Item Code' in headers and 'Name' in headers:
            return idx
    return 1


def load_inventory_rows(path: str) -> list[dict]:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    if not rows:
        return []

    header_row_idx = _detect_header_row(rows)
    headers = [_cell_str(h) for h in rows[header_row_idx]]
    missing = [col for col in EXPECTED_COLUMNS if col not in headers]
    if missing:
        raise CommandError(
            f'Missing columns: {", ".join(missing)}. '
            f'Expected: {", ".join(EXPECTED_COLUMNS)}'
        )

    data = []
    for row in rows[header_row_idx + 1:]:
        if not row or not any(not _is_blank(v) for v in row):
            continue
        row_data = {}
        for idx, header in enumerate(headers):
            if header and idx < len(row):
                row_data[header] = row[idx]
        code = _parse_item_code(row_data.get('Item Code'))
        name = _cell_str(row_data.get('Name'))
        if not code or not name:
            continue
        data.append(row_data)
    return data


def row_to_item_defaults(row: dict) -> dict:
    return {
        'item_code': _parse_item_code(row.get('Item Code')),
        'name': _cell_str(row.get('Name'))[:200],
        'item_type': _parse_item_type(row.get('Type')),
        'status': 'active',
        'purchase_price': _purchase_price(row),
        'selling_price': _parse_decimal(row.get('Sales Price')),
        'minimum_stock': _parse_decimal(row.get('Stock Alert')),
        'unit': _normalize_unit(row.get('Unit')),
        'available_qty': _parse_decimal(row.get('Available')),
    }


class Command(BaseCommand):
    help = 'Import inventory items from Zoho-style inventory export (.xlsx).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            required=True,
            help='Path to inventory workbook',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Parse and report without saving',
        )
        parser.add_argument(
            '--replace-all',
            action='store_true',
            help='Delete all existing items before import (clears stock via DB cascade)',
        )
        parser.add_argument(
            '--warehouse',
            type=str,
            default='',
            help='Warehouse name for Available stock (default: first active warehouse)',
        )

    def _clear_items(self):
        table = Item._meta.db_table
        with connection.cursor() as cursor:
            cursor.execute(
                f'TRUNCATE TABLE {connection.ops.quote_name(table)} RESTART IDENTITY CASCADE'
            )

    def _resolve_warehouse(self, name: str) -> Warehouse:
        if name:
            warehouse = Warehouse.objects.filter(name__iexact=name, is_active=True).first()
            if not warehouse:
                raise CommandError(f'Warehouse not found: {name}')
            return warehouse
        warehouse = Warehouse.objects.filter(is_active=True).order_by('pk').first()
        if not warehouse:
            raise CommandError('No active warehouse found. Create a warehouse first.')
        return warehouse

    def handle(self, *args, **options):
        path = options['file']
        dry_run = options['dry_run']
        replace_all = options['replace_all']

        try:
            rows = load_inventory_rows(path)
        except FileNotFoundError as exc:
            raise CommandError(str(exc)) from exc

        if not rows:
            raise CommandError('No inventory rows found in file.')

        tax_code = TaxCode.objects.filter(code='VAT5', is_active=True).first()
        if not tax_code:
            tax_code = TaxCode.objects.filter(rate=Decimal('5.00'), is_active=True).first()
        if not tax_code and not dry_run:
            raise CommandError('VAT 5% tax code (VAT5) not found. Run seed_tax_codes first.')

        warehouse = None if dry_run else self._resolve_warehouse(options['warehouse'])
        stats = {
            'created': 0,
            'stock_rows': 0,
            'cleared': 0,
        }

        @transaction.atomic
        def run_import():
            if replace_all:
                stats['cleared'] = Item.objects.count()
                self._clear_items()

            for row in rows:
                defaults = row_to_item_defaults(row)
                available_qty = defaults.pop('available_qty')
                code = defaults.pop('item_code')

                item = Item(**defaults, tax_code=tax_code)
                item.item_code = code
                item.save()
                stats['created'] += 1

                if warehouse and available_qty > 0:
                    Stock.objects.create(
                        item=item,
                        warehouse=warehouse,
                        quantity=available_qty,
                    )
                    stats['stock_rows'] += 1

            if dry_run:
                transaction.set_rollback(True)

        run_import()

        prefix = '[DRY RUN] ' if dry_run else ''
        cleared_msg = f'{stats["cleared"]} cleared, ' if replace_all else ''
        warehouse_msg = f' into {warehouse.name}' if warehouse else ''
        self.stdout.write(self.style.SUCCESS(
            f'{prefix}Inventory import complete — '
            f'{cleared_msg}'
            f'{stats["created"]} items created, '
            f'{stats["stock_rows"]} stock rows{warehouse_msg}.'
        ))
