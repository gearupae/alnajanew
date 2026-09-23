"""Shared vendor bill payment recording (single and bulk)."""
from decimal import Decimal
from datetime import date

from django.db.models import Q

from apps.finance.models import (
    Payment,
    BankAccount,
    JournalEntry,
    JournalEntryLine,
    Account,
    AccountType,
    AccountMapping,
)

CASH_PAYMENT_METHODS = frozenset({'cash', 'petty_cash', 'cash_in_office'})

CASH_PAYMENT_LOOKUPS = {
    'petty_cash': {
        'label': 'Petty Cash',
        'name_patterns': ['petty cash'],
        'fallback_codes': ['1020'],
    },
    'cash_in_office': {
        'label': 'Cash in Office',
        'name_patterns': ['cash in office', 'cash in hand', 'cash on hand'],
        'fallback_codes': ['1010'],
    },
    'cash': {
        'label': 'Cash',
        'name_patterns': ['cash in hand', 'cash on hand', 'cash in office'],
        'fallback_codes': ['1010'],
    },
}


def is_cash_payment_method(payment_method: str) -> bool:
    if payment_method in CASH_PAYMENT_METHODS:
        return True
    return payment_method.startswith('cash_') and payment_method not in CASH_PAYMENT_METHODS


def resolve_cash_gl_account(payment_method: str):
    """Resolve the GL account for a cash-style payment method."""
    lookup = CASH_PAYMENT_LOOKUPS.get(payment_method)
    if lookup:
        name_query = Q()
        for pattern in lookup['name_patterns']:
            name_query |= Q(name__icontains=pattern)

        account = Account.objects.filter(is_active=True, is_cash_account=True).filter(name_query).first()
        if account:
            return account

        for code in lookup.get('fallback_codes', []):
            account = Account.objects.filter(is_active=True, code=code).first()
            if account:
                return account

        return None

    if payment_method.startswith('cash_'):
        account_id = payment_method.split('_', 1)[1]
        return Account.objects.filter(pk=account_id, is_active=True).first()

    return None


def record_vendor_bill_payment(
    bill,
    amount,
    payment_method,
    bank_account,
    payment_date,
    reference,
    user,
):
    """
    Record payment for a vendor bill and post clearing journal entry.
    Returns (payment, None) on success or (None, error_message) on failure.
    """
    if bill.status == 'draft':
        return None, 'Bill must be posted to accounting before making payment.'

    if bill.balance <= 0:
        return None, 'Bill is already fully paid.'

    amount = Decimal(amount)
    if amount <= 0:
        return None, 'Amount must be positive.'

    if amount > bill.balance:
        amount = bill.balance

    if payment_method in ('bank', 'cheque') and not bank_account:
        return None, 'Bank account is required for bank transfer and cheque payments.'

    cash_gl_account = None
    stored_payment_method = payment_method
    if is_cash_payment_method(payment_method):
        cash_gl_account = resolve_cash_gl_account(payment_method)
        if not cash_gl_account:
            label = CASH_PAYMENT_LOOKUPS.get(payment_method, {}).get('label', 'Cash')
            return None, f'{label} account is not configured in Chart of Accounts.'
        stored_payment_method = 'cash'

    payment = Payment.objects.create(
        payment_type='made',
        payment_method=stored_payment_method,
        payment_date=payment_date,
        party_type='vendor',
        party_id=bill.vendor_id,
        party_name=bill.vendor.name,
        amount=amount,
        reference=reference or bill.bill_number,
        bill=bill,
        bank_account=bank_account,
        cash_account=cash_gl_account,
        status='draft',
    )

    ap_account = AccountMapping.get_account_or_default('vendor_payment_ap_clear', '2000')
    if not ap_account:
        ap_account = Account.objects.filter(
            account_type=AccountType.LIABILITY, is_active=True, name__icontains='payable'
        ).first()

    if not ap_account:
        payment.delete()
        return None, 'Accounts Payable account not configured.'

    if payment_method in ('bank', 'cheque', 'card') and bank_account and bank_account.gl_account:
        bank_gl_account = bank_account.gl_account
    elif is_cash_payment_method(payment_method):
        bank_gl_account = cash_gl_account
    else:
        payment.delete()
        return None, 'Bank account GL is required for this payment method.'

    if not bank_gl_account:
        payment.delete()
        return None, 'Bank/Cash account not configured.'

    journal = JournalEntry.objects.create(
        date=payment_date,
        reference=payment.payment_number,
        description=f"Payment Voucher: {bill.bill_number} - {bill.vendor.name}",
        entry_type='standard',
        source_module='payment',
    )

    JournalEntryLine.objects.create(
        journal_entry=journal,
        account=ap_account,
        description=f"AP Clearing - {bill.bill_number}",
        debit=amount,
        credit=Decimal('0.00'),
    )

    JournalEntryLine.objects.create(
        journal_entry=journal,
        account=bank_gl_account,
        description=f"Payment to {bill.vendor.name}",
        debit=Decimal('0.00'),
        credit=amount,
    )

    journal.calculate_totals()

    try:
        journal.post(user)
        payment.journal_entry = journal
        payment.status = 'confirmed'
        payment.allocated_amount = amount
        payment.save()

        bill.paid_amount += amount
        if bill.paid_amount >= bill.total_amount:
            bill.status = 'paid'
        else:
            bill.status = 'partial'
        bill.save(update_fields=['paid_amount', 'status'])

        return payment, None
    except Exception as exc:
        journal.delete()
        payment.delete()
        return None, f'Error posting payment: {exc}'


def resolve_bank_account(payment_method, bank_account_id):
    """Return active BankAccount for bank/cheque/card payments, or None for cash."""
    if is_cash_payment_method(payment_method):
        return None

    if payment_method not in ('bank', 'cheque', 'card'):
        return None

    if bank_account_id:
        bank_account = BankAccount.objects.filter(pk=bank_account_id, is_active=True).first()
        if not bank_account:
            raise ValueError('Invalid bank account selected.')
        return bank_account

    if payment_method == 'bank':
        bank_account = BankAccount.objects.filter(is_active=True).first()
        if not bank_account:
            raise ValueError('Bank account is required for bank transfer payments.')
        return bank_account

    raise ValueError('Bank account is required for cheque payments.')


def parse_payment_date(payment_date_str):
    """Parse YYYY-MM-DD payment date string; default to today."""
    from datetime import datetime

    if not payment_date_str:
        return date.today()
    try:
        return datetime.strptime(payment_date_str, '%Y-%m-%d').date()
    except ValueError:
        return date.today()
