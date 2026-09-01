"""
Seed UAE fire fighting chart of accounts, tax codes, and account mappings
from erp_project/data/uae_firefighting_coa_seed.json.

Data-only — uses existing Account, TaxCode, and AccountMapping models.
Idempotent: safe to re-run (update_or_create by code / transaction_type).

Usage:
  python manage.py seed_uae_firefighting_coa
  python manage.py seed_uae_firefighting_coa --dry-run
"""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.finance.models import Account, AccountCategory, AccountMapping, AccountType, TaxCode

DATA_FILE = Path(settings.BASE_DIR) / 'data' / 'uae_firefighting_coa_seed.json'

TYPE_MAP = {
    'ASSET': AccountType.ASSET,
    'LIABILITY': AccountType.LIABILITY,
    'EQUITY': AccountType.EQUITY,
    'INCOME': AccountType.INCOME,
    'EXPENSE': AccountType.EXPENSE,
}

SUBTYPE_CATEGORY = {
    'CASH': AccountCategory.CASH_BANK,
    'BANK': AccountCategory.CASH_BANK,
    'RECEIVABLE': AccountCategory.TRADE_RECEIVABLES,
    'TAX_ASSET': AccountCategory.TAX_RECEIVABLES,
    'INVENTORY': AccountCategory.INVENTORY,
    'PREPAID': AccountCategory.PREPAID,
    'DEPOSIT': AccountCategory.OTHER_CURRENT_ASSETS,
    'CLEARING': AccountCategory.OTHER_CURRENT_ASSETS,
    'CONTRA_ASSET': AccountCategory.ACCUMULATED_DEPRECIATION,
    'ACC_DEPRECIATION': AccountCategory.ACCUMULATED_DEPRECIATION,
    'CONTRACT_WIP': AccountCategory.OTHER_CURRENT_ASSETS,
    'CONTRACT_ASSET': AccountCategory.OTHER_CURRENT_ASSETS,
    'RETENTION': AccountCategory.OTHER_CURRENT_ASSETS,
    'FIXED_ASSET': AccountCategory.FIXED_ASSETS_OTHER,
    'INTANGIBLE': AccountCategory.INTANGIBLE_ASSETS,
    'PAYABLE': AccountCategory.TRADE_PAYABLES,
    'ACCRUAL': AccountCategory.ACCRUED_LIABILITIES,
    'ADVANCE': AccountCategory.OTHER_CURRENT_LIABILITIES,
    'CONTRACT_LIABILITY': AccountCategory.OTHER_CURRENT_LIABILITIES,
    'PROVISION': AccountCategory.ACCRUED_LIABILITIES,
    'TAX_LIABILITY': AccountCategory.TAX_PAYABLES,
    'PAYROLL': AccountCategory.OTHER_CURRENT_LIABILITIES,
    'BORROWING': AccountCategory.LONG_TERM_LIABILITIES,
    'LEASE': AccountCategory.LONG_TERM_LIABILITIES,
    'SUSPENSE': AccountCategory.OTHER_CURRENT_LIABILITIES,
    'CAPITAL': AccountCategory.CAPITAL,
    'RESERVE': AccountCategory.RESERVES,
    'RETAINED_EARNINGS': AccountCategory.RETAINED_EARNINGS,
    'OPENING': AccountCategory.CAPITAL,
    'DISTRIBUTION': AccountCategory.CAPITAL,
    'CONTRACT_REVENUE': AccountCategory.OPERATING_REVENUE,
    'SERVICE_REVENUE': AccountCategory.OPERATING_REVENUE,
    'REVENUE': AccountCategory.OPERATING_REVENUE,
    'CONTRA_REVENUE': AccountCategory.OPERATING_REVENUE,
    'CONTRACT_COST': AccountCategory.COST_OF_SALES,
    'CONTRA_COST': AccountCategory.COST_OF_SALES,
    'OPEX': AccountCategory.ADMIN_EXPENSE,
    'DEPRECIATION': AccountCategory.DEPRECIATION_EXPENSE,
    'OTHER_INCOME': AccountCategory.OTHER_INCOME,
    'FX': AccountCategory.OTHER_INCOME,
    'FINANCE_COST': AccountCategory.BANKING_EXPENSE,
    'OTHER_EXPENSE': AccountCategory.OTHER_EXPENSE,
    'TAX': AccountCategory.ADMIN_EXPENSE,
}

TAX_TYPE_MAP = {
    'SR5': 'standard',
    'IMP': 'standard',
    'RC': 'standard',
    'ZR': 'zero',
    'DZ': 'zero',
    'EX': 'exempt',
    'OS': 'out_of_scope',
}

MODULE_MAP = {
    'sales': {
        'sales_invoice_receivable', 'sales_invoice_revenue', 'sales_invoice_vat',
        'sales_invoice_discount', 'customer_receipt', 'customer_receipt_ar_clear', 'sales_return',
    },
    'purchase': {
        'vendor_bill_payable', 'vendor_bill_expense', 'vendor_bill_vat',
        'vendor_payment', 'vendor_payment_ap_clear', 'purchase_return', 'security_cheque_forfeiture',
    },
    'expense_claim': {
        'expense_claim_expense', 'expense_claim_vat', 'expense_claim_payable',
        'expense_claim_payment', 'expense_claim_clear',
    },
    'payroll': {
        'payroll_salary_expense', 'payroll_salary_payable', 'payroll_gratuity_expense',
        'payroll_gratuity_payable', 'payroll_pension_expense', 'payroll_pension_payable',
        'payroll_wps_deduction', 'payroll_payment', 'payroll_payment_clear',
    },
    'banking': {'bank_charges', 'bank_interest_income', 'bank_interest_expense', 'bank_transfer'},
    'inventory': {
        'inventory_asset', 'inventory_cogs', 'inventory_grn_clearing',
        'inventory_variance', 'inventory_damage_expense', 'inventory_revaluation',
    },
    'property': {
        'pdc_control', 'cheques_in_hand', 'pdc_bounce_charges', 'pdc_bounce_income',
        'trade_debtors_property', 'rental_income', 'rental_income_commercial',
        'security_deposit_liability', 'security_deposit_forfeit',
        'maintenance_income', 'service_charge_income',
    },
    'general': {
        'fixed_asset', 'fixed_asset_clearing', 'depreciation_expense', 'accumulated_depreciation',
        'gain_on_disposal', 'loss_on_disposal', 'disposal_proceeds',
        'project_expense', 'project_revenue', 'project_expense_clearing', 'project_wip',
        'vat_output', 'vat_input', 'vat_payable',
        'corporate_tax_expense', 'corporate_tax_payable',
        'customer_advance_liability', 'vendor_advance_asset', 'vendor_security_deposit',
        'security_cheques_payable',
        'fx_gain', 'fx_loss', 'retained_earnings', 'opening_balance_equity', 'suspense', 'rounding',
        'intercompany_receivable', 'intercompany_payable',
    },
}

VALID_TRANSACTION_TYPES = {code for code, _ in AccountMapping.TRANSACTION_TYPE_CHOICES}


def _module_for(transaction_type: str) -> str:
    for module, types in MODULE_MAP.items():
        if transaction_type in types:
            return module
    return 'general'


def _category_for(row: dict) -> str | None:
    subtype = row.get('subtype') or ''
    if subtype in SUBTYPE_CATEGORY:
        return SUBTYPE_CATEGORY[subtype]
    acct_type = row.get('type', '')
    if acct_type == 'INCOME':
        return AccountCategory.OPERATING_REVENUE
    if acct_type == 'EXPENSE':
        return AccountCategory.ADMIN_EXPENSE
    return AccountCategory.OTHER_CURRENT_ASSETS if acct_type == 'ASSET' else AccountCategory.OTHER_CURRENT_LIABILITIES


class Command(BaseCommand):
    help = 'Seed UAE fire fighting COA, tax codes, and account mappings from JSON data file'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Report without saving')

    def handle(self, *args, **options):
        if not DATA_FILE.exists():
            self.stderr.write(self.style.ERROR(f'Missing data file: {DATA_FILE}'))
            return

        payload = json.loads(DATA_FILE.read_text(encoding='utf-8'))
        dry_run = options['dry_run']

        @transaction.atomic
        def run():
            acct_created = acct_updated = 0
            tax_created = tax_updated = 0
            map_created = map_updated = 0
            map_skipped = 0

            account_by_code: dict[str, Account] = {}

            for row in payload.get('accounts', []):
                code = row['code']
                subtype = row.get('subtype', '')
                defaults = {
                    'name': row['name'],
                    'account_type': TYPE_MAP[row['type']],
                    'account_category': _category_for(row),
                    'is_active': True,
                    'is_cash_account': subtype in ('CASH', 'BANK'),
                    'is_contra_account': subtype in ('CONTRA_ASSET', 'ACC_DEPRECIATION', 'CONTRA_REVENUE', 'CONTRA_COST'),
                    'is_fixed_deposit': code == '1015',
                    'overdraft_allowed': subtype == 'BANK' and code == '2300',
                    'description': f"Subtype: {subtype}" if subtype else '',
                }
                if dry_run:
                    if Account.objects.filter(code=code).exists():
                        acct_updated += 1
                    else:
                        acct_created += 1
                    continue
                account, created = Account.objects.update_or_create(code=code, defaults=defaults)
                account_by_code[code] = account
                if created:
                    acct_created += 1
                else:
                    acct_updated += 1

            if not dry_run:
                account_by_code.update(
                    {a.code: a for a in Account.objects.filter(code__in=[r['code'] for r in payload.get('accounts', [])])}
                )

            for row in payload.get('tax_codes', []):
                code = row['code']
                output_acct = account_by_code.get(row.get('output_account') or '') if row.get('output_account') else None
                input_acct = account_by_code.get(row.get('input_account') or '') if row.get('input_account') else None
                if not output_acct and row.get('output_account'):
                    output_acct = Account.objects.filter(code=row['output_account'], is_active=True).first()
                if not input_acct and row.get('input_account'):
                    input_acct = Account.objects.filter(code=row['input_account'], is_active=True).first()
                defaults = {
                    'name': row['name'],
                    'tax_type': TAX_TYPE_MAP.get(code, 'standard'),
                    'rate': Decimal(str(row['rate'])),
                    'description': row.get('name', ''),
                    'is_default': code == 'SR5',
                    'is_active': True,
                    'sales_account': output_acct,
                    'purchase_account': input_acct,
                }
                if dry_run:
                    if TaxCode.objects.filter(code=code).exists():
                        tax_updated += 1
                    else:
                        tax_created += 1
                    continue
                tax, created = TaxCode.objects.update_or_create(code=code, defaults=defaults)
                if created:
                    tax_created += 1
                else:
                    tax_updated += 1

            if not dry_run:
                TaxCode.objects.exclude(code__in=[r['code'] for r in payload.get('tax_codes', [])]).update(
                    is_default=False, is_active=False
                )
                sr5 = TaxCode.objects.filter(code='SR5', is_active=True).first()
                if sr5:
                    from apps.inventory.models import Item

                    Item.objects.filter(tax_code__code='VAT5').update(tax_code=sr5)
                    Item.objects.filter(tax_code__isnull=True).update(tax_code=sr5)

            all_mappings = dict(payload.get('account_mapping', {}))
            all_mappings.update(payload.get('new_mapping_keys_required', {}))

            for trans_type, acct_code in all_mappings.items():
                if trans_type not in VALID_TRANSACTION_TYPES:
                    map_skipped += 1
                    continue
                if dry_run:
                    if AccountMapping.objects.filter(transaction_type=trans_type).exists():
                        map_updated += 1
                    else:
                        map_created += 1
                    continue
                account = account_by_code.get(acct_code) or Account.objects.filter(
                    code=acct_code, is_active=True
                ).first()
                if not account:
                    self.stdout.write(self.style.WARNING(f'  Skip mapping {trans_type}: account {acct_code} missing'))
                    map_skipped += 1
                    continue
                _, created = AccountMapping.objects.update_or_create(
                    transaction_type=trans_type,
                    defaults={
                        'module': _module_for(trans_type),
                        'account': account,
                        'is_mandatory': True,
                    },
                )
                if created:
                    map_created += 1
                else:
                    map_updated += 1

            if not dry_run:
                from apps.settings_app.models import CompanySettings

                cs = CompanySettings.get_settings()
                co = payload.get('company', {})
                cs.company_name = cs.company_name or 'Safety Point'
                cs.currency = co.get('currency', 'AED')
                cs.timezone = 'Asia/Dubai'
                if not cs.address:
                    cs.address = 'Mussafah Industrial Area, Abu Dhabi, United Arab Emirates'
                cs.save()

            if dry_run:
                transaction.set_rollback(True)

            return acct_created, acct_updated, tax_created, tax_updated, map_created, map_updated, map_skipped

        results = run()
        self.stdout.write(self.style.SUCCESS(
            f'\nUAE fire fighting COA seed complete:\n'
            f'  accounts: {results[0]} created, {results[1]} updated\n'
            f'  tax codes: {results[2]} created, {results[3]} updated\n'
            f'  mappings: {results[4]} created, {results[5]} updated, {results[6]} skipped (unsupported keys)'
        ))
