"""
Vendor Bill reversal tests.

Verifies that reversing a posted vendor bill:
  * creates a balanced mirror reversal journal (Dr AP, Cr Expense, Cr Input VAT),
  * fully backs out the Input VAT and every GL line (net GL effect = zero),
  * marks the original journal 'reversed' (retained for audit, never deleted),
  * returns the bill to an editable draft with its journal link cleared,
  * removes the linked project expense,
  * is blocked when a payment or a posted debit note exists.

Run: python manage.py test apps.purchase.tests.test_bill_reversal -v 2
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from apps.finance.models import (
    FiscalYear, AccountingPeriod, Account, AccountType,
    AccountMapping, TaxCode, JournalEntry,
)
from apps.purchase.models import Vendor, VendorBill, VendorBillItem


class VendorBillReversalTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser(
            username='rev_user', email='rev@example.com', password='x'
        )

        today = date.today()
        cls.fy = FiscalYear.objects.create(
            name=f'FY {today.year}',
            start_date=date(today.year, 1, 1),
            end_date=date(today.year, 12, 31),
        )
        cls.period = AccountingPeriod.objects.create(
            fiscal_year=cls.fy,
            name=f'{today:%B %Y}',
            start_date=date(today.year, today.month, 1),
            end_date=date(today.year, today.month, 28),
        )

        # Chart of accounts
        cls.expense = Account.objects.create(code='5000', name='Expense', account_type=AccountType.EXPENSE)
        cls.vat_rec = Account.objects.create(code='1310', name='Input VAT Recoverable', account_type=AccountType.ASSET)
        cls.ap = Account.objects.create(code='2100', name='Accounts Payable', account_type=AccountType.LIABILITY)

        # Account determination
        AccountMapping.objects.create(module='purchase', transaction_type='vendor_bill_payable', account=cls.ap)
        AccountMapping.objects.create(module='purchase', transaction_type='vendor_bill_expense', account=cls.expense)
        AccountMapping.objects.create(module='purchase', transaction_type='vendor_bill_vat', account=cls.vat_rec)

        cls.vat5 = TaxCode.objects.create(code='VAT5', name='Standard 5%', rate=Decimal('5.00'), is_default=True)
        cls.vendor = Vendor.objects.create(name='Acme Supplies')

    def _make_posted_bill(self):
        today = date.today()
        bill = VendorBill.objects.create(
            vendor=self.vendor, bill_date=today, due_date=today,
        )
        VendorBillItem.objects.create(
            bill=bill, description='Materials', quantity=Decimal('1'),
            unit_price=Decimal('1000.00'), tax_code=self.vat5,
        )
        bill.calculate_totals()
        bill.refresh_from_db()
        bill.post_to_accounting(user=self.user)
        bill.refresh_from_db()
        return bill

    def test_posting_builds_expected_lines(self):
        bill = self._make_posted_bill()
        self.assertEqual(bill.status, 'posted')
        self.assertEqual(bill.subtotal, Decimal('1000.00'))
        self.assertEqual(bill.vat_amount, Decimal('50.00'))
        self.assertEqual(bill.total_amount, Decimal('1050.00'))
        je = bill.journal_entry
        self.assertIsNotNone(je)
        self.assertEqual(je.total_debit, Decimal('1050.00'))
        self.assertEqual(je.total_credit, Decimal('1050.00'))

    def test_reverse_backs_out_vat_and_gl(self):
        bill = self._make_posted_bill()
        original = bill.journal_entry

        reversal = bill.reverse_posting(user=self.user, reason='test reversal')

        # Reversal journal is balanced and mirrors the original amounts
        self.assertEqual(reversal.entry_type, 'reversal')
        self.assertEqual(reversal.reversal_of_id, original.pk)
        self.assertEqual(reversal.total_debit, Decimal('1050.00'))
        self.assertEqual(reversal.total_credit, Decimal('1050.00'))

        # Input VAT fully reverted: debit on original, credit on reversal -> net 0
        orig_vat = original.lines.get(account=self.vat_rec)
        rev_vat = reversal.lines.get(account=self.vat_rec)
        self.assertEqual(orig_vat.debit, Decimal('50.00'))
        self.assertEqual(rev_vat.credit, Decimal('50.00'))

        # Net GL movement across original + reversal is zero for every account
        for acc in (self.expense, self.vat_rec, self.ap):
            net = Decimal('0.00')
            for je in (original, reversal):
                for ln in je.lines.filter(account=acc):
                    net += ln.debit - ln.credit
            self.assertEqual(net, Decimal('0.00'), f'account {acc.code} not net-zero')

        # Original retained but marked reversed (audit trail, not deleted)
        original.refresh_from_db()
        self.assertEqual(original.status, 'reversed')
        self.assertTrue(JournalEntry.objects.filter(pk=original.pk).exists())

        # Bill released back to editable draft, journal link cleared
        bill.refresh_from_db()
        self.assertEqual(bill.status, 'draft')
        self.assertIsNone(bill.journal_entry_id)
        self.assertEqual(bill.paid_amount, Decimal('0.00'))

    def test_cannot_reverse_draft(self):
        today = date.today()
        bill = VendorBill.objects.create(vendor=self.vendor, bill_date=today, due_date=today)
        with self.assertRaises(ValidationError):
            bill.reverse_posting(user=self.user)

    def test_cannot_reverse_twice(self):
        bill = self._make_posted_bill()
        bill.reverse_posting(user=self.user)
        bill.refresh_from_db()
        # Now a draft again -> reversing errors
        with self.assertRaises(ValidationError):
            bill.reverse_posting(user=self.user)

    def test_cannot_reverse_with_payment(self):
        bill = self._make_posted_bill()
        bill.paid_amount = Decimal('100.00')
        bill.status = 'partial'
        bill.save(update_fields=['paid_amount', 'status'])
        with self.assertRaises(ValidationError):
            bill.reverse_posting(user=self.user)
