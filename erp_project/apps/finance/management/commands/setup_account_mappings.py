"""
Setup Default Account Mappings
SAP/Oracle-style Account Determination

This command sets up default account mappings based on existing chart of accounts.
Run this ONCE after migrating to the new account mapping system.
"""
from django.core.management.base import BaseCommand
from apps.finance.models import Account, AccountMapping, AccountingSettings


class Command(BaseCommand):
    help = 'Setup default account mappings for SAP/Oracle-style posting'

    # Maps account code -> transaction types (standard Safety Point COA codes)
    DEFAULT_MAPPINGS = {
        '1100': ['sales_invoice_receivable', 'customer_receipt_ar_clear'],
        '4100': ['sales_invoice_revenue'],
        '2200': ['sales_invoice_vat'],
        '2100': ['vendor_bill_payable', 'vendor_payment_ap_clear'],
        '2010': ['inventory_grn_clearing'],
        '5800': ['vendor_bill_expense', 'expense_claim_expense', 'payroll_gratuity_expense', 'security_cheque_forfeiture'],
        '1310': ['vendor_bill_vat', 'expense_claim_vat'],
        '2320': ['expense_claim_payable'],
        '1200': ['inventory_asset'],
        '5100': ['inventory_cogs'],
        '5200': ['payroll_salary_expense'],
        '2330': ['payroll_salary_payable'],
        '2340': ['payroll_gratuity_payable'],
        '5700': ['bank_charges'],
        '4920': ['bank_interest_income'],
        '5710': ['bank_interest_expense'],
        '4930': ['fx_gain'],
        '5720': ['fx_loss'],
        '3200': ['retained_earnings'],
        '3100': ['opening_balance_equity'],
        '1210': ['pdc_control'],
        '4910': ['pdc_bounce_income'],
        '6800': ['pdc_bounce_charges'],
        '1900': ['suspense'],
        '5910': ['rounding'],
        '1020': ['customer_receipt', 'vendor_payment', 'expense_claim_payment', 'payroll_payment'],
    }

    ALTERNATIVES = {
        '1020': ['1010'],
    }

    MODULE_MAP = {
        'sales': [
            'sales_invoice_receivable', 'sales_invoice_revenue', 'sales_invoice_vat',
            'sales_invoice_discount', 'customer_receipt', 'customer_receipt_ar_clear',
        ],
        'purchase': [
            'vendor_bill_payable', 'vendor_bill_expense', 'vendor_bill_vat',
            'vendor_payment', 'vendor_payment_ap_clear', 'security_cheque_forfeiture',
        ],
        'inventory': [
            'inventory_asset', 'inventory_cogs', 'inventory_grn_clearing',
            'inventory_variance', 'inventory_damage_expense',
        ],
        'property': ['pdc_control', 'pdc_bounce_charges', 'pdc_bounce_income'],
        'expense_claim': [
            'expense_claim_expense', 'expense_claim_vat', 'expense_claim_payable',
            'expense_claim_payment', 'expense_claim_clear',
        ],
        'payroll': [
            'payroll_salary_expense', 'payroll_salary_payable', 'payroll_gratuity_expense',
            'payroll_gratuity_payable', 'payroll_pension_expense', 'payroll_pension_payable',
            'payroll_wps_deduction', 'payroll_payment', 'payroll_payment_clear',
        ],
        'banking': ['bank_charges', 'bank_interest_income', 'bank_interest_expense', 'bank_transfer'],
        'general': ['fx_gain', 'fx_loss', 'retained_earnings', 'opening_balance_equity', 'suspense', 'rounding'],
    }

    def get_module(self, transaction_type):
        for module, types in self.MODULE_MAP.items():
            if transaction_type in types:
                return module
        return 'general'

    def find_account(self, code):
        account = Account.objects.filter(code=code, is_active=True).first()
        if account:
            return account
        for alt_code in self.ALTERNATIVES.get(code, []):
            account = Account.objects.filter(code=alt_code, is_active=True).first()
            if account:
                return account
        return None

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Setting up default account mappings...'))

        created_count = 0
        skipped_count = 0
        failed_count = 0

        for code, transaction_types in self.DEFAULT_MAPPINGS.items():
            account = self.find_account(code)

            if not account:
                self.stdout.write(self.style.WARNING(
                    f'Account {code} not found. Skipping: {", ".join(transaction_types)}'
                ))
                failed_count += len(transaction_types)
                continue

            for trans_type in transaction_types:
                existing = AccountMapping.objects.filter(transaction_type=trans_type).first()
                if existing:
                    self.stdout.write(self.style.WARNING(
                        f'Mapping for {trans_type} already exists -> {existing.account.code}'
                    ))
                    skipped_count += 1
                    continue

                AccountMapping.objects.create(
                    module=self.get_module(trans_type),
                    transaction_type=trans_type,
                    account=account,
                )
                self.stdout.write(self.style.SUCCESS(
                    f'Created: {trans_type} -> {account.code} ({account.name})'
                ))
                created_count += 1

        AccountingSettings.get_settings()
        self.stdout.write(self.style.SUCCESS('Accounting settings initialized.'))
        self.stdout.write(self.style.SUCCESS(
            f'\nSummary: {created_count} created, {skipped_count} skipped, {failed_count} failed'
        ))

        for module_code, module_name in AccountMapping.MODULE_CHOICES:
            is_configured = AccountMapping.is_fully_configured(module_code)
            status = '✓' if is_configured else '✗'
            self.stdout.write(
                f'{status} {module_name}: {"Configured" if is_configured else "Incomplete"}'
            )
