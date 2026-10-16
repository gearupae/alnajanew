"""
One-off repair: re-post finance payments that were booked to the hardcoded
AR/AP clearing account instead of the "Post to Account" the user selected.

Context (A.2): before the fix in `_post_document_linked_payment`, any finance
payment with a party posted its counter leg to the AR/AP clearing mapping
(e.g. AP 2010), ignoring `Payment.account`. This command corrects already-
confirmed payments by REVERSING the mis-posted journal (FTA-compliant audit
trail; the original stays in the GL, offset by a posted reversal) and RE-POSTING
a correct journal that uses the selected account, then repointing
`Payment.journal_entry` so a later Cancel still mirrors the correct entry.

It never touches VAT accounts and only runs when the payment's period / filed
VAT return is not locked (the reversal itself enforces this).

Usage:
    python manage.py repair_payment_posted_account --dry-run
    python manage.py repair_payment_posted_account                      # default payments
    python manage.py repair_payment_posted_account --payments PV-2026-0002 PV-2026-0003

Idempotent: a payment whose journal already debits/credits the selected
account is reported as "already correct" and skipped.
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction

from apps.finance.models import JournalEntry, JournalEntryLine, Payment

DEFAULT_PAYMENTS = ['PV-2026-0002', 'PV-2026-0003']


class Command(BaseCommand):
    help = 'Reverse-and-repost finance payments mis-booked to AR/AP clearing instead of the selected Post to Account.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Show what would change without writing.')
        parser.add_argument('--payments', nargs='+', default=DEFAULT_PAYMENTS,
                            help='Payment numbers to repair (default: %s).' % ', '.join(DEFAULT_PAYMENTS))

    def handle(self, *args, **opts):
        dry = opts['dry_run']
        actor = get_user_model().objects.filter(is_superuser=True).order_by('id').first()

        for number in opts['payments']:
            try:
                payment = Payment.objects.get(payment_number=number)
            except Payment.DoesNotExist:
                self.stderr.write(self.style.WARNING(f'{number}: not found, skipping.'))
                continue
            self._repair_one(payment, actor, dry)

    def _repair_one(self, payment, actor, dry):
        number = payment.payment_number
        if payment.status != 'confirmed':
            self.stdout.write(f'{number}: status={payment.status} (only confirmed payments are repaired), skipping.')
            return

        journal = payment.journal_entry
        if not journal or journal.status != 'posted':
            self.stdout.write(f'{number}: no posted journal attached, skipping.')
            return

        counter = payment.account
        if counter is None:
            self.stdout.write(f'{number}: no Post to Account selected, nothing to honour, skipping.')
            return

        funds = payment.get_funds_gl_account()
        if funds is None:
            self.stderr.write(self.style.WARNING(f'{number}: no bank/cash funds account resolvable, skipping.'))
            return

        amount = (payment.allocated_amount or payment.amount).quantize(Decimal('0.01'))

        # The counter leg is the debit for 'made', the credit for 'received'.
        is_made = payment.payment_type == 'made'
        current = {
            (line.account_id, 'dr' if line.debit else 'cr'): line
            for line in journal.lines.all()
        }
        counter_side = 'dr' if is_made else 'cr'
        if (counter.id, counter_side) in current:
            self.stdout.write(self.style.SUCCESS(
                f'{number}: journal already posts {counter.code} on the correct side — already correct, skipping.'))
            return

        self.stdout.write(f'\n{number} ({payment.get_payment_type_display()}, {payment.amount}):')
        self.stdout.write(f'  BEFORE journal {journal.entry_number}:')
        for line in journal.lines.all().order_by('id'):
            self.stdout.write(f'    {line.account.code} {line.account.name}  Dr={line.debit} Cr={line.credit}')
        self.stdout.write(f'  WILL REVERSE it and REPOST: '
                          + (f'Dr {counter.code} / Cr {funds.code}' if is_made
                             else f'Dr {funds.code} / Cr {counter.code}') + f'  {amount}')

        if dry:
            self.stdout.write(self.style.NOTICE('  [dry-run] no changes written.'))
            return

        with transaction.atomic():
            payment = Payment.objects.select_for_update().get(pk=payment.pk)
            journal = payment.journal_entry

            # 1) Reverse the mis-posted journal (enforces period / filed-VAT locks).
            journal.reverse(user=actor,
                            reason=f'A2 repair: {number} re-posted to selected account {counter.code}')

            # 2) Re-post a correct journal honouring the selected account.
            new_journal = JournalEntry.objects.create(
                date=payment.payment_date,
                reference=payment.payment_number,
                description=f'{payment.get_payment_type_display()}: {payment.party_name} '
                            f'(A2 repair - posted to {counter.code})',
                entry_type='standard',
                source_module='payment',
            )
            if is_made:
                JournalEntryLine.objects.create(journal_entry=new_journal, account=counter,
                                                description=f'Payment to {payment.party_name}', debit=amount)
                JournalEntryLine.objects.create(journal_entry=new_journal, account=funds,
                                                description=f'Payment to {payment.party_name}', credit=amount)
            else:
                JournalEntryLine.objects.create(journal_entry=new_journal, account=funds,
                                                description=f'Payment from {payment.party_name}', debit=amount)
                JournalEntryLine.objects.create(journal_entry=new_journal, account=counter,
                                                description=f'{counter.code} - {payment.party_name}', credit=amount)
            new_journal.calculate_totals()
            new_journal.post(actor)

            payment.journal_entry = new_journal
            payment.save(update_fields=['journal_entry'])

        self.stdout.write(self.style.SUCCESS(
            f'  REPAIRED: new journal {new_journal.entry_number} posted; payment repointed.'))
