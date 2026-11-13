"""Sales tax invoice number: SI/{month}/{year}/{n} (sequence resets each calendar month)."""

from __future__ import annotations

import re

from django.utils import timezone

_SI_PATTERN = re.compile(r'^SI/(\d{1,2})/(\d{4})/(\d+)$', re.IGNORECASE)


def generate_sales_invoice_number(invoice_date=None, *, exclude_pk=None) -> str:
    """Next tax invoice number for the given invoice date (defaults to today)."""
    from .models import Invoice

    if invoice_date is None:
        invoice_date = timezone.localdate()

    month = invoice_date.month
    year = invoice_date.year
    prefix = f'SI/{month}/{year}/'

    qs = Invoice.objects.filter(invoice_number__istartswith=prefix)
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)

    max_seq = 0
    for number in qs.values_list('invoice_number', flat=True):
        match = _SI_PATTERN.match(number.strip())
        if match and int(match.group(1)) == month and int(match.group(2)) == year:
            max_seq = max(max_seq, int(match.group(3)))

    return f'{prefix}{max_seq + 1}'
