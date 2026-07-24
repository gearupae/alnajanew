"""
Link legacy payments to invoices/bills by matching reference to document number.

Usage:
    python manage.py backfill_payment_document_links
    python manage.py backfill_payment_document_links --dry-run
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.finance.models import Payment


class Command(BaseCommand):
    help = 'Backfill Payment.invoice / Payment.bill from reference for legacy rows.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Report matches without saving',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        linked_invoice = 0
        linked_bill = 0
        skipped = 0

        qs = Payment.objects.filter(is_active=True).order_by('pk')
        for payment in qs:
            if payment.invoice_id or payment.bill_id:
                skipped += 1
                continue

            invoice = payment.resolve_linked_invoice()
            if invoice:
                if dry_run:
                    self.stdout.write(
                        f'  WOULD link payment {payment.payment_number} → invoice {invoice.invoice_number}'
                    )
                else:
                    payment.invoice = invoice
                    payment.save(update_fields=['invoice'])
                linked_invoice += 1
                continue

            bill = payment.resolve_linked_bill()
            if bill:
                if dry_run:
                    self.stdout.write(
                        f'  WOULD link payment {payment.payment_number} → bill {bill.bill_number}'
                    )
                else:
                    payment.bill = bill
                    payment.save(update_fields=['bill'])
                linked_bill += 1

        prefix = '[DRY RUN] ' if dry_run else ''
        self.stdout.write(self.style.SUCCESS(
            f'{prefix}Done. Invoices linked: {linked_invoice}, bills linked: {linked_bill}, '
            f'already linked: {skipped}.'
        ))
