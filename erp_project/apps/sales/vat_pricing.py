"""VAT-inclusive / exclusive line amount splitting for sales documents."""
from decimal import Decimal, ROUND_HALF_UP

TWOPLACES = Decimal('0.01')


def quantize_money(value):
    return Decimal(value).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def split_line_amounts(gross, vat_rate, inclusive):
    """
    Split a line gross amount into taxable base and VAT.

    When inclusive and vat_rate > 0, entered gross is back-calculated so
    taxable_base + line_vat == gross exactly (2-decimal fils rounding).
    Zero-rated/exempt: base = gross, VAT = 0.
    Exclusive mode: taxable = gross, VAT = gross * rate/100.
    """
    gross = quantize_money(gross)
    vat_rate = Decimal(vat_rate or 0)

    if inclusive and vat_rate > 0:
        divisor = Decimal('1') + vat_rate / Decimal('100')
        taxable_base = quantize_money(gross / divisor)
        line_vat = quantize_money(gross - taxable_base)
        if taxable_base + line_vat != gross:
            taxable_base = quantize_money(gross - line_vat)
        return taxable_base, line_vat

    taxable_base = gross
    if vat_rate > 0:
        line_vat = quantize_money(taxable_base * vat_rate / Decimal('100'))
    else:
        line_vat = Decimal('0.00')
    return taxable_base, line_vat


def line_uses_inclusive_pricing(item):
    """Document-level toggle with per-line legacy fallback."""
    parent = None
    if getattr(item, 'estimate_id', None):
        try:
            parent = item.estimate
        except Exception:
            parent = None
    elif getattr(item, 'invoice_id', None):
        try:
            parent = item.invoice
        except Exception:
            parent = None

    if parent is not None:
        return bool(parent.prices_include_vat or item.is_vat_inclusive)
    return bool(item.is_vat_inclusive)


def sync_document_line_vat_flags(document):
    """Align line is_vat_inclusive with document prices_include_vat and recalc."""
    inclusive = bool(document.prices_include_vat)
    for item in document.items.all():
        item.is_vat_inclusive = inclusive
        item.save()


def default_prices_include_vat():
    from apps.finance.models import AccountingSettings

    return AccountingSettings.get_settings().default_prices_include_vat


def estimate_vat_toggle_editable(estimate, revision_hint=False):
    if not estimate.pk:
        return True
    if estimate.status == 'draft':
        return True
    return bool(revision_hint)
