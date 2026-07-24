"""
Management command: seed_advance_mappings

Creates AccountMapping entries for the Advances module.
Skips entries that already exist.

Usage:
    python manage.py seed_advance_mappings
"""
from django.core.management.base import BaseCommand


MAPPINGS = [
    {
        'transaction_type': 'customer_advance_liability',
        'account_code': '2310',
        'expected_name': 'Customer Advance',
        'forbidden_categories': {'accrued_liabilities', 'tax_payables'},
        'module': 'sales',
        'description': 'Customer Advance — Liability account credited on advance receipt',
        'account_defaults': {
            'name': 'Customer Advance',
            'account_type': 'liability',
            'account_category': 'other_current_liabilities',
            'description': 'Advances received from customers before invoicing.',
        },
    },
    {
        'transaction_type': 'vendor_advance_asset',
        'account_code': '1320',
        'expected_name': 'Advance to Vendor',
        'forbidden_categories': {'tax_receivables'},
        'module': 'purchase',
        'description': 'Advance to Vendor — Asset account debited on advance payment',
        'account_defaults': {
            'name': 'Advance to Vendor',
            'account_type': 'asset',
            'account_category': 'other_current_assets',
            'description': 'Advance payments made to vendors.',
        },
    },
    {
        'transaction_type': 'vendor_security_deposit',
        'account_code': '1360',
        'expected_name': 'Vendor Security Deposit',
        'forbidden_categories': set(),
        'module': 'purchase',
        'description': 'Vendor Security Deposit — debited when security cheque is issued',
        'account_defaults': {
            'name': 'Vendor Security Deposit',
            'account_type': 'asset',
            'account_category': 'other_current_assets',
            'description': 'Security deposits placed with vendors.',
        },
    },
    {
        'transaction_type': 'security_cheques_payable',
        'account_code': '2360',
        'expected_name': 'Security Cheques Payable',
        'forbidden_categories': set(),
        'module': 'purchase',
        'description': 'Security Cheques Payable — credited when security cheque is issued',
        'account_defaults': {
            'name': 'Security Cheques Payable',
            'account_type': 'liability',
            'account_category': 'other_current_liabilities',
            'description': 'Security cheques issued to vendors.',
        },
    },
]


class Command(BaseCommand):
    help = (
        'Seeds AccountMapping entries for the Advances module. '
        'Run after seed_advance_accounts.'
    )

    def _resolve_account(self, mapping):
        from apps.finance.models import Account

        code = mapping['account_code']
        expected_name = mapping['expected_name']
        forbidden = mapping['forbidden_categories']

        account = Account.objects.filter(code=code, is_active=True).first()
        if account:
            if account.name == expected_name:
                return account
            if account.account_category in forbidden:
                self.stdout.write(
                    self.style.ERROR(
                        f'  ERROR  Account {code} is "{account.name}" '
                        f'({account.account_category}) — not the advance account. '
                        f'Run seed_advance_accounts or fix_advance_mappings.'
                    )
                )
                return None
            self.stdout.write(
                self.style.WARNING(
                    f'  WARN  Account {code} exists as "{account.name}" '
                    f'but expected "{expected_name}". Using dedicated advance code only.'
                )
            )
            return None

        account, created = Account.objects.get_or_create(
            code=code,
            defaults={
                **mapping['account_defaults'],
                'is_active': True,
            },
        )
        if created:
            self.stdout.write(
                self.style.SUCCESS(f'  CREATED  account {code} — {expected_name}')
            )
        return account

    def handle(self, *args, **options):
        from apps.finance.models import AccountMapping

        for mapping in MAPPINGS:
            ttype = mapping['transaction_type']

            if AccountMapping.objects.filter(transaction_type=ttype).exists():
                existing = AccountMapping.objects.get(transaction_type=ttype)
                acct = existing.account
                if acct.account_category in mapping['forbidden_categories']:
                    self.stdout.write(
                        self.style.ERROR(
                            f'  ERROR  {ttype} mapped to {acct.code} ({acct.name}) — '
                            f'wrong category. Run fix_advance_mappings.'
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f'  SKIP  {ttype} — already mapped to {existing.account.code}'
                        )
                    )
                continue

            account = self._resolve_account(mapping)
            if not account:
                continue

            AccountMapping.objects.create(
                transaction_type=ttype,
                account=account,
                module=mapping['module'],
                description=mapping['description'],
                is_mandatory=True,
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f'  CREATED  {ttype} → {account.code} ({account.name})'
                )
            )

        self.stdout.write(self.style.SUCCESS('Done.'))
