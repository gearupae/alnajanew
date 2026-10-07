"""Point AR account mappings at postable leaf accounts instead of parent 1100."""

from django.db import migrations


AR_MAPPING_TYPES = (
    'sales_invoice_receivable',
    'customer_receipt_ar_clear',
)

AR_LEAF_FALLBACK_CODES = ('1201', '1202', '1110', '1210', '1120')


def _is_leaf(Account, account):
    if not account:
        return False
    return not Account.objects.filter(parent_id=account.pk, is_active=True).exists()


def _best_ar_leaf(Account):
    for code in AR_LEAF_FALLBACK_CODES:
        account = Account.objects.filter(code=code, is_active=True).first()
        if account and _is_leaf(Account, account):
            return account
    return None


def fix_ar_mapping_leaf_accounts(apps, schema_editor):
    Account = apps.get_model('finance', 'Account')
    AccountMapping = apps.get_model('finance', 'AccountMapping')

    leaf = _best_ar_leaf(Account)
    if not leaf:
        return

    for transaction_type in AR_MAPPING_TYPES:
        mapping = AccountMapping.objects.filter(transaction_type=transaction_type).first()
        if not mapping:
            continue
        if not _is_leaf(Account, mapping.account):
            mapping.account = leaf
            mapping.save(update_fields=['account'])


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0037_bankaccount_optional_account_number'),
    ]

    operations = [
        migrations.RunPython(fix_ar_mapping_leaf_accounts, migrations.RunPython.noop),
    ]
