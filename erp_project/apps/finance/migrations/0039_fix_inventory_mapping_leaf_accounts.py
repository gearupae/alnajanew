"""Point inventory account mappings at postable leaf accounts instead of parent controls."""

from django.db import migrations


INVENTORY_MAPPING_TYPES = {
    'inventory_asset': ('1300', '1310', '1320', '1330', '1340', '1500'),
    'inventory_cogs': ('5010', '5020', '5030', '5040', '5100', '5200'),
    'inventory_grn_clearing': ('2025', '2010', '2020'),
    'inventory_variance': ('5200', '5020', '5030'),
    'inventory_damage_expense': ('5200', '5020'),
    'inventory_revaluation': ('1350', '5200'),
}


def _is_leaf(Account, account):
    if not account:
        return False
    return not Account.objects.filter(parent_id=account.pk, is_active=True).exists()


def _best_leaf(Account, fallback_codes, *, name_hints=()):
    if name_hints:
        for hint in name_hints:
            for account in Account.objects.filter(is_active=True, name__icontains=hint).order_by('code'):
                if _is_leaf(Account, account):
                    return account
    for code in fallback_codes:
        account = Account.objects.filter(code=code, is_active=True).first()
        if account and _is_leaf(Account, account):
            if not name_hints or any(h.lower() in account.name.lower() for h in name_hints):
                return account
    for code in fallback_codes:
        account = Account.objects.filter(code=code, is_active=True).first()
        if account and _is_leaf(Account, account):
            return account
    return None


def fix_inventory_mapping_leaf_accounts(apps, schema_editor):
    Account = apps.get_model('finance', 'Account')
    AccountMapping = apps.get_model('finance', 'AccountMapping')

    name_hints_by_type = {
        'inventory_asset': ('inventory',),
        'inventory_cogs': ('cost', 'cogs', 'goods sold'),
        'inventory_grn_clearing': ('grn', 'clear', 'gr/i'),
        'inventory_variance': ('variance', 'shrinkage', 'write-off', 'write off'),
        'inventory_damage_expense': ('damage', 'write-off', 'write off'),
        'inventory_revaluation': ('revaluation', 'inventory'),
    }

    for transaction_type, fallback_codes in INVENTORY_MAPPING_TYPES.items():
        mapping = AccountMapping.objects.filter(transaction_type=transaction_type).first()
        if not mapping:
            continue
        if _is_leaf(Account, mapping.account):
            current_name = (mapping.account.name or '').lower()
            hints = name_hints_by_type.get(transaction_type, ())
            if not hints or any(h in current_name for h in hints):
                continue
        leaf = _best_leaf(
            Account,
            fallback_codes,
            name_hints=name_hints_by_type.get(transaction_type, ()),
        )
        if leaf:
            mapping.account = leaf
            mapping.save(update_fields=['account'])


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0038_fix_ar_mapping_leaf_accounts'),
    ]

    operations = [
        migrations.RunPython(fix_inventory_mapping_leaf_accounts, migrations.RunPython.noop),
    ]
