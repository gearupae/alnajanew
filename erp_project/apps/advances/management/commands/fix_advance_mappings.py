"""
Re-point advance account mappings that were incorrectly linked to tax/accrual accounts.

Usage:
    python manage.py fix_advance_mappings
"""
from django.core.management.base import BaseCommand
from django.db import transaction


FIXES = [
    {
        'transaction_type': 'vendor_advance_asset',
        'forbidden_categories': {'tax_receivables'},
        'target_code': '1320',
        'target_defaults': {
            'name': 'Advance to Vendor',
            'account_type': 'asset',
            'account_category': 'other_current_assets',
            'description': 'Advance payments made to vendors.',
            'is_active': True,
        },
    },
    {
        'transaction_type': 'customer_advance_liability',
        'forbidden_categories': {'accrued_liabilities', 'tax_payables'},
        'target_code': '2310',
        'target_defaults': {
            'name': 'Customer Advance',
            'account_type': 'liability',
            'account_category': 'other_current_liabilities',
            'description': 'Advances received from customers before invoicing.',
            'is_active': True,
        },
    },
]


class Command(BaseCommand):
    help = 'Fix advance mappings that point at VAT or accrual accounts instead of dedicated advance accounts.'

    @transaction.atomic
    def handle(self, *args, **options):
        from apps.finance.models import Account, AccountMapping

        fixed = 0
        for spec in FIXES:
            mapping = AccountMapping.objects.filter(
                transaction_type=spec['transaction_type']
            ).select_related('account').first()
            if not mapping:
                self.stdout.write(
                    self.style.WARNING(f'  SKIP  No mapping for {spec["transaction_type"]}')
                )
                continue

            acct = mapping.account
            if acct.account_category not in spec['forbidden_categories']:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'  OK  {spec["transaction_type"]} → {acct.code} ({acct.name})'
                    )
                )
                continue

            target, created = Account.objects.get_or_create(
                code=spec['target_code'],
                defaults=spec['target_defaults'],
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'  CREATED  account {target.code} — {target.name}'
                    )
                )

            old_code = acct.code
            mapping.account = target
            mapping.save(update_fields=['account'])
            fixed += 1
            self.stdout.write(
                self.style.WARNING(
                    f'  FIXED  {spec["transaction_type"]}: {old_code} ({acct.name}) '
                    f'→ {target.code} ({target.name})'
                )
            )
            self.stdout.write(
                self.style.WARNING(
                    '         Historical journals on the old account may need manual reclassification.'
                )
            )

        self.stdout.write(self.style.SUCCESS(f'Done. {fixed} mapping(s) updated.'))
