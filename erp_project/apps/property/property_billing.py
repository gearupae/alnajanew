"""Property billing helpers — rent invoices, deposits, unit occupancy."""
from datetime import timedelta
from decimal import Decimal

from .models import Lease, RentInvoice, SecurityDeposit


def vat_rate_for_lease(lease):
    """Commercial leases are 5% VAT; residential are exempt."""
    if lease and lease.lease_type == 'commercial':
        return Decimal('5.00')
    return Decimal('0.00')


def sync_unit_occupancy(lease, old_unit=None, old_status=None):
    """Keep unit occupancy aligned with active leases."""
    if old_unit and old_unit != lease.unit:
        _free_unit_if_no_active_leases(old_unit)

    if not lease.unit:
        return

    if lease.status == 'active':
        if lease.unit.status != 'occupied':
            lease.unit.status = 'occupied'
            lease.unit.save(update_fields=['status'])
    elif lease.status in ('terminated', 'expired', 'renewed'):
        _free_unit_if_no_active_leases(lease.unit)


def _free_unit_if_no_active_leases(unit):
    has_active = unit.leases.filter(is_active=True, status='active').exists()
    if not has_active and unit.status == 'occupied':
        unit.status = 'available'
        unit.save(update_fields=['status'])


def _payment_interval_months(lease):
    if lease.payment_frequency == 'monthly':
        return 1
    if lease.payment_frequency == 'quarterly':
        return 3
    if lease.payment_frequency == 'semi_annual':
        return 6
    return 12


def generate_rent_invoices_for_lease(lease, user):
    """Create draft rent invoices aligned with the lease payment schedule."""
    vat_rate = vat_rate_for_lease(lease)
    payment_amount = lease.payment_amount
    interval_months = _payment_interval_months(lease)
    created = []

    current_date = lease.start_date
    for _ in range(lease.number_of_cheques):
        period_start = current_date
        next_date = current_date + timedelta(days=interval_months * 30)
        period_end = next_date - timedelta(days=1)

        if RentInvoice.objects.filter(
            lease=lease, period_start=period_start, is_active=True
        ).exists():
            current_date = next_date
            continue

        invoice = RentInvoice.objects.create(
            tenant=lease.tenant,
            lease=lease,
            unit=lease.unit,
            invoice_date=period_start,
            due_date=period_start,
            period_start=period_start,
            period_end=period_end,
            rent_amount=payment_amount,
            vat_rate=vat_rate,
            created_by=user,
        )
        created.append(invoice)
        current_date = next_date

    return created


def ensure_security_deposit_record(lease, user):
    """Create a pending security deposit record when the lease specifies one."""
    if lease.security_deposit <= 0:
        return None
    existing = lease.security_deposits.filter(is_active=True).exclude(
        status='refunded'
    ).first()
    if existing:
        return existing
    return SecurityDeposit.objects.create(
        lease=lease,
        tenant=lease.tenant,
        amount=lease.security_deposit,
        created_by=user,
    )
