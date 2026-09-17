"""
Import customers from Excel/CSV.

Supported formats:
- Standard template (erp_project/import_templates/customers_import.csv)
- Zoho export ("Customers - ..." title row, then ID/Name/... headers)

Usage:
    python manage.py import_customers_xlsx --file customers.xlsx
    python manage.py import_customers_xlsx --file customers.xlsx --replace-all
"""
from __future__ import annotations

import csv
from decimal import Decimal, InvalidOperation

import openpyxl
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from apps.crm.models import Customer

TEMPLATE_COLUMNS = [
    'Customer Code',
    'Customer Name',
    'Email',
    'Phone',
    'Company',
    'Address',
    'City',
    'Country',
    'Website',
    'TRN Number',
    'Customer Type',
    'Business Segment',
    'Status',
    'Job Type',
    'Scope',
    'Payment Terms',
    'Credit Limit (AED)',
    'Primary Project Code',
    'Assigned Sales Employee Code',
    'Notes',
]

ZOHO_COLUMNS = {
    'ID': 'customer_number',
    'Name': 'name',
    'Company': 'company',
    'Email': 'email',
    'Phone': 'phone',
    'Address': 'address',
    'City': 'city',
    'Country': 'country',
    'TRN': 'trn',
    'Payment Terms Name': 'payment_terms',
    'Website': 'website',
    'Tags': 'tags',
    'Secondary Email': 'secondary_email',
    'Created By Name': 'created_by_name',
}


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
    return text[:20]


def _parse_phone(value) -> str:
    phone = _cell_str(value)
    if not phone:
        return ''
    if '&' in phone:
        phone = phone.split('&', 1)[0].strip()
    if ',' in phone:
        phone = phone.split(',', 1)[0].strip()
    return phone[:20]


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


def _parse_scope(value) -> list:
    text = _cell_str(value).lower()
    if not text:
        return []
    allowed = {'ff', 'fa', 'em', 'fls', 'mep'}
    return [part.strip() for part in text.split(',') if part.strip() in allowed]


def _normalize_row(row: dict, fmt: str) -> dict:
    if fmt == 'template':
        name = _cell_str(row.get('Customer Name'))
        if not name:
            return {}
        customer_type = _cell_str(row.get('Customer Type')).lower() or 'customer'
        status = _cell_str(row.get('Status')).lower() or 'active'
        segment = _cell_str(row.get('Business Segment')).lower()
        return {
            'customer_number': _cell_str(row.get('Customer Code')),
            'name': name,
            'email': _cell_str(row.get('Email')),
            'phone': _parse_phone(row.get('Phone')),
            'company': _cell_str(row.get('Company')),
            'address': _cell_str(row.get('Address')),
            'city': _cell_str(row.get('City')),
            'country': _cell_str(row.get('Country')) or 'United Arab Emirates',
            'website': _cell_str(row.get('Website')),
            'trn': _parse_trn(row.get('TRN Number')),
            'customer_type': customer_type if customer_type in ('lead', 'customer') else 'customer',
            'business_segment': segment if segment in ('b2b', 'b2c') else '',
            'status': status if status in ('active', 'inactive', 'prospect') else 'active',
            'job_type': _cell_str(row.get('Job Type')).lower(),
            'scope': _parse_scope(row.get('Scope')),
            'payment_terms': _cell_str(row.get('Payment Terms')) or 'Net 30',
            'credit_limit': _parse_decimal(row.get('Credit Limit (AED)')),
            'notes': _cell_str(row.get('Notes')),
        }

    excel_name = _cell_str(row.get('Name'))
    excel_company = _cell_str(row.get('Company'))
    if not excel_name and not excel_company:
        return {}
    # Excel Name is the customer/business name; Company column (when present) is preferred.
    # When both exist, Name is treated as the contact person.
    customer_company = excel_company or excel_name
    contact_name = excel_name if excel_company else ''
    trn = _parse_trn(row.get('TRN'))
    notes_parts = []
    for label, key in (
        ('Secondary Email', 'secondary_email'),
        ('Tags', 'tags'),
        ('Created By', 'created_by_name'),
    ):
        value = _cell_str(row.get(key if fmt == 'zoho_mapped' else label))
        if value:
            notes_parts.append(f'{label}: {value}')
    return {
        'customer_number': _cell_str(row.get('ID')),
        'name': contact_name,
        'email': _cell_str(row.get('Email')),
        'phone': _parse_phone(row.get('Phone')),
        'company': customer_company,
        'address': _cell_str(row.get('Address')),
        'city': _cell_str(row.get('City')),
        'country': _cell_str(row.get('Country')) or 'United Arab Emirates',
        'website': '',
        'trn': trn,
        'customer_type': 'customer',
        'business_segment': 'b2b' if trn else '',
        'status': 'active',
        'job_type': '',
        'scope': [],
        'payment_terms': _cell_str(row.get('Payment Terms Name')) or 'Net 30',
        'credit_limit': Decimal('0.00'),
        'notes': '\n'.join(notes_parts),
    }


def _detect_format(headers: list[str]) -> str:
    normalized = {_cell_str(h) for h in headers if _cell_str(h)}
    if 'Customer Code' in normalized and 'Customer Name' in normalized:
        return 'template'
    if 'ID' in normalized and 'Name' in normalized:
        return 'zoho'
    raise CommandError(
        'Unrecognized workbook format. Expected template or Zoho export columns.'
    )


def _read_xlsx(path: str) -> tuple[list[dict], str]:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    if not rows:
        return [], 'template'

    header_row_idx = 0
    first_cell = _cell_str(rows[0][0]) if rows[0] else ''
    if first_cell.lower().startswith('customers -') or first_cell.lower().startswith('customer -'):
        header_row_idx = 1
    if len(rows) <= header_row_idx:
        return [], 'template'

    headers = [_cell_str(h) for h in rows[header_row_idx]]
    fmt = _detect_format(headers)
    data = []
    for row in rows[header_row_idx + 1:]:
        if not row or not any(not _is_blank(v) for v in row):
            continue
        row_data = {}
        for idx, header in enumerate(headers):
            if header and idx < len(row):
                row_data[header] = row[idx]
        normalized = _normalize_row(row_data, fmt)
        if normalized:
            data.append(normalized)
    return data, fmt


def _read_csv(path: str) -> tuple[list[dict], str]:
    with open(path, newline='', encoding='utf-8-sig') as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            return [], 'template'
        fmt = _detect_format(list(reader.fieldnames))
        data = []
        for row in reader:
            normalized = _normalize_row(row, fmt)
            if normalized:
                data.append(normalized)
        return data, fmt


def load_customer_rows(path: str) -> tuple[list[dict], str]:
    lower = path.lower()
    if lower.endswith('.csv'):
        return _read_csv(path)
    if lower.endswith(('.xlsx', '.xlsm')):
        return _read_xlsx(path)
    raise CommandError('Unsupported file type. Use .xlsx or .csv')


class Command(BaseCommand):
    help = 'Import customers from Excel/CSV (template or Zoho export).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            required=True,
            help='Path to customers import workbook or CSV',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Parse and report without saving',
        )
        parser.add_argument(
            '--update-existing',
            action='store_true',
            help='Update customers matched by customer number or name',
        )
        parser.add_argument(
            '--replace-all',
            action='store_true',
            help='Delete all existing customers before import (clears related rows via DB cascade)',
        )

    def _clear_customers(self):
        table = Customer._meta.db_table
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
            rows, fmt = load_customer_rows(path)
        except FileNotFoundError as exc:
            raise CommandError(str(exc)) from exc

        if not rows:
            raise CommandError('No customer rows found in file.')

        stats = {'created': 0, 'updated': 0, 'skipped': 0, 'cleared': 0}

        @transaction.atomic
        def run_import():
            if replace_all:
                stats['cleared'] = Customer.objects.count()
                self._clear_customers()

            for defaults in rows:
                code = defaults.pop('customer_number')
                scope = defaults.pop('scope', [])
                job_type = defaults.pop('job_type', '')
                if job_type and job_type not in dict(Customer.JOB_TYPE_CHOICES):
                    job_type = ''

                customer = None
                if code:
                    customer = Customer.objects.filter(customer_number=code).first()
                if customer is None and defaults.get('company'):
                    customer = Customer.objects.filter(
                        company__iexact=defaults['company'],
                    ).first()
                if customer is None and defaults.get('name'):
                    customer = Customer.objects.filter(name__iexact=defaults['name']).first()

                if customer:
                    if not update_existing:
                        stats['skipped'] += 1
                        continue
                    for field, value in defaults.items():
                        setattr(customer, field, value)
                    customer.scope = scope
                    customer.job_type = job_type
                    customer.save()
                    stats['updated'] += 1
                    continue

                customer = Customer(**defaults, scope=scope, job_type=job_type)
                if code:
                    customer.customer_number = code
                customer.save()
                stats['created'] += 1

            if dry_run:
                transaction.set_rollback(True)

        run_import()

        prefix = '[DRY RUN] ' if dry_run else ''
        cleared_msg = f'{stats["cleared"]} cleared, ' if replace_all else ''
        self.stdout.write(self.style.SUCCESS(
            f'{prefix}Customer import complete ({fmt}) — '
            f'{cleared_msg}'
            f'{stats["created"]} created, '
            f'{stats["updated"]} updated, '
            f'{stats["skipped"]} skipped.'
        ))
