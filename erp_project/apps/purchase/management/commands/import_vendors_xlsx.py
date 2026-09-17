"""
Import vendors from Excel/CSV using erp_project/import_templates/vendors_import.csv columns.

Usage:
    python manage.py import_vendors_xlsx --file "/path/to/vendors_import 2026.xlsx"
    python manage.py import_vendors_xlsx --file vendors.xlsx --dry-run
"""
from __future__ import annotations

import csv
from decimal import Decimal, InvalidOperation

import openpyxl
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from apps.purchase.models import Vendor

EXPECTED_COLUMNS = [
    'Vendor Code',
    'Vendor Name',
    'Contact Person',
    'Email',
    'Phone',
    'Address',
    'City',
    'Country',
    'TRN Number',
    'Payment Terms',
    'Credit Limit (AED)',
    'Status',
    'Notes',
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


def _parse_trn(value) -> str:
    if _is_blank(value):
        return ''
    if isinstance(value, float):
        return str(int(value))
    text = str(value).strip()
    if text.endswith('.0'):
        text = text[:-2]
    return text


def _parse_decimal(value) -> Decimal:
    if _is_blank(value):
        return Decimal('0.00')
    if isinstance(value, str):
        text = value.replace(',', '').strip()
        if not text:
            return Decimal('0.00')
        try:
            return Decimal(text)
        except InvalidOperation:
            return Decimal('0.00')
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return Decimal('0.00')


def _parse_status(value) -> str:
    status = _cell_str(value).lower() or 'active'
    if status not in ('active', 'inactive'):
        raise CommandError(f'Invalid status "{value}". Use active or inactive.')
    return status


def _parse_phone(value) -> str:
    phone = _cell_str(value)
    if not phone:
        return ''
    if ',' in phone:
        phone = phone.split(',', 1)[0].strip()
    return phone[:20]


def _read_xlsx(path: str) -> list[dict]:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    if not rows:
        return []

    headers = [_cell_str(h) for h in rows[0]]
    missing = [col for col in EXPECTED_COLUMNS if col not in headers]
    if missing:
        raise CommandError(
            f'Missing columns: {", ".join(missing)}. '
            f'Expected: {", ".join(EXPECTED_COLUMNS)}'
        )

    data = []
    for row in rows[1:]:
        if not row or not any(not _is_blank(v) for v in row):
            continue
        row_data = {}
        for idx, header in enumerate(headers):
            if header and idx < len(row):
                row_data[header] = row[idx]
        if not _cell_str(row_data.get('Vendor Name')):
            continue
        data.append(row_data)
    return data


def _read_csv(path: str) -> list[dict]:
    with open(path, newline='', encoding='utf-8-sig') as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            return []
        missing = [col for col in EXPECTED_COLUMNS if col not in reader.fieldnames]
        if missing:
            raise CommandError(
                f'Missing columns: {", ".join(missing)}. '
                f'Expected: {", ".join(EXPECTED_COLUMNS)}'
            )
        data = []
        for row in reader:
            if not _cell_str(row.get('Vendor Name')):
                continue
            data.append(row)
        return data


def load_vendor_rows(path: str) -> list[dict]:
    lower = path.lower()
    if lower.endswith('.csv'):
        return _read_csv(path)
    if lower.endswith(('.xlsx', '.xlsm')):
        return _read_xlsx(path)
    raise CommandError('Unsupported file type. Use .xlsx or .csv')


def row_to_defaults(row: dict) -> dict:
    return {
        'name': _cell_str(row.get('Vendor Name')),
        'contact_person': _cell_str(row.get('Contact Person')),
        'email': _cell_str(row.get('Email')),
        'phone': _parse_phone(row.get('Phone')),
        'address': _cell_str(row.get('Address')),
        'city': _cell_str(row.get('City')),
        'country': _cell_str(row.get('Country')) or 'United Arab Emirates',
        'trn': _parse_trn(row.get('TRN Number')),
        'payment_terms': _cell_str(row.get('Payment Terms')) or 'Net 30',
        'credit_limit': _parse_decimal(row.get('Credit Limit (AED)')),
        'status': _parse_status(row.get('Status')),
        'notes': _cell_str(row.get('Notes')),
    }


class Command(BaseCommand):
    help = 'Import vendors from vendors_import.xlsx or .csv template.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            required=True,
            help='Path to vendors import workbook or CSV',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Parse and report without saving',
        )
        parser.add_argument(
            '--update-existing',
            action='store_true',
            help='Update vendors matched by vendor number or name',
        )
        parser.add_argument(
            '--replace-all',
            action='store_true',
            help='Delete all existing vendors before import (clears related PO/bill rows via DB cascade)',
        )

    def _clear_vendors(self):
        table = Vendor._meta.db_table
        with connection.cursor() as cursor:
            cursor.execute(
                f'TRUNCATE TABLE {connection.ops.quote_name(table)} RESTART IDENTITY CASCADE'
            )

    def handle(self, *args, **options):
        path = options['file']
        dry_run = options['dry_run']
        update_existing = options['update_existing']
        replace_all = options['replace_all']

        if replace_all and update_existing:
            raise CommandError('Use either --replace-all or --update-existing, not both.')

        try:
            rows = load_vendor_rows(path)
        except FileNotFoundError as exc:
            raise CommandError(str(exc)) from exc

        if not rows:
            raise CommandError('No vendor rows found in file.')

        stats = {'created': 0, 'updated': 0, 'skipped': 0, 'cleared': 0}

        @transaction.atomic
        def run_import():
            if replace_all:
                stats['cleared'] = Vendor.objects.count()
                self._clear_vendors()

            for row in rows:
                code = _cell_str(row.get('Vendor Code'))
                defaults = row_to_defaults(row)

                vendor = None
                if code:
                    vendor = Vendor.objects.filter(vendor_number=code).first()
                if vendor is None:
                    vendor = Vendor.objects.filter(name__iexact=defaults['name']).first()

                if vendor:
                    if not update_existing:
                        stats['skipped'] += 1
                        continue
                    for field, value in defaults.items():
                        setattr(vendor, field, value)
                    vendor.save()
                    stats['updated'] += 1
                    continue

                vendor = Vendor(**defaults)
                if code:
                    vendor.vendor_number = code
                vendor.save()
                stats['created'] += 1

            if dry_run:
                transaction.set_rollback(True)

        run_import()

        prefix = '[DRY RUN] ' if dry_run else ''
        cleared_msg = ''
        if replace_all:
            cleared_msg = f'{stats["cleared"]} cleared, '
        self.stdout.write(self.style.SUCCESS(
            f'{prefix}Vendor import complete — '
            f'{cleared_msg}'
            f'{stats["created"]} created, '
            f'{stats["updated"]} updated, '
            f'{stats["skipped"]} skipped.'
        ))
