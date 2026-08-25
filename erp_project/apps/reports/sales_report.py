"""Standard ERP sales report — invoicing, collections, receivables, quotations."""
from __future__ import annotations

from decimal import Decimal

from django.db.models import Count, DecimalField, Exists, ExpressionWrapper, F, OuterRef, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.advances.models import CustomerAdvance
from apps.crm.models import Customer
from apps.crm.utils import get_sales_employee_queryset, salesperson_display_name
from apps.finance.models import Payment
from apps.sales.models import Estimate, Invoice, SalesCreditNote

from .sales_report_attribution import (
    customer_salesperson_q,
    estimate_salesperson_label,
    estimate_salesperson_q,
    invoice_salesperson_label,
    invoice_salesperson_q,
)

INVOICE_REVENUE_STATUSES = ('posted', 'sent', 'paid', 'partial', 'overdue')
PAYMENT_RECEIVED_STATUSES = ('confirmed', 'reconciled')


def _pct(numerator: Decimal, denominator: Decimal) -> int:
    if not denominator:
        return 0
    return int((numerator / denominator * Decimal('100')).quantize(Decimal('1')))


def _money_agg(qs, *, subtotal_field='subtotal', vat_field='vat_amount', total_field='total_amount'):
    return qs.aggregate(
        count=Count('id'),
        subtotal=Coalesce(Sum(subtotal_field), Decimal('0.00')),
        vat=Coalesce(Sum(vat_field), Decimal('0.00')),
        total=Coalesce(Sum(total_field), Decimal('0.00')),
    )


def _period_invoices(start_date, end_date, salesperson=''):
    return (
        Invoice.objects.filter(
            is_active=True,
            invoice_date__gte=start_date,
            invoice_date__lte=end_date,
            status__in=INVOICE_REVENUE_STATUSES,
        )
        .filter(invoice_salesperson_q(salesperson))
        .select_related('customer', 'estimate', 'estimate__assigned_to', 'customer__assigned_salesperson')
        .order_by('-invoice_date', '-id')
    )


def _period_payments(start_date, end_date, salesperson=''):
    qs = Payment.objects.filter(
        is_active=True,
        payment_type='received',
        party_type='customer',
        status__in=PAYMENT_RECEIVED_STATUSES,
        payment_date__gte=start_date,
        payment_date__lte=end_date,
    ).order_by('-payment_date', '-id')
    if salesperson:
        qs = qs.filter(
            party_id__in=Customer.objects.filter(is_active=True)
            .filter(customer_salesperson_q(salesperson))
            .values('pk')
            .distinct()
        )
    return qs


def _period_receipts(start_date, end_date, salesperson=''):
    return (
        CustomerAdvance.objects.filter(
            is_active=True,
            status='posted',
            date__gte=start_date,
            date__lte=end_date,
        )
        .filter(customer_salesperson_q(salesperson, prefix='customer__'))
        .select_related('customer', 'customer__assigned_salesperson')
        .order_by('-date', '-id')
    )


def _period_estimates(start_date, end_date, salesperson=''):
    return Estimate.objects.filter(
        is_active=True,
        date__gte=start_date,
        date__lte=end_date,
    ).filter(estimate_salesperson_q(salesperson))


def _collected_totals(start_date, end_date, salesperson=''):
    zero = Decimal('0.00')
    payments_agg = _period_payments(start_date, end_date, salesperson).aggregate(
        count=Count('id'),
        total=Coalesce(Sum('amount'), zero),
    )
    receipts_agg = _money_agg(
        _period_receipts(start_date, end_date, salesperson),
        subtotal_field='amount',
        vat_field='vat_amount',
        total_field='total_amount',
    )
    total = (payments_agg['total'] or zero) + (receipts_agg['total'] or zero)
    count = (payments_agg['count'] or 0) + (receipts_agg['count'] or 0)
    return {'count': count, 'total': total, 'payments': payments_agg, 'receipts': receipts_agg}


def _build_revenue_by_customer(*, invoice_qs, payment_qs, receipt_qs):
    """Aggregate invoiced and collected amounts by customer."""
    from collections import defaultdict

    by_customer = defaultdict(
        lambda: {
            'customer_name': '',
            'invoiced_total': Decimal('0.00'),
            'collected_total': Decimal('0.00'),
            'invoice_count': 0,
        }
    )

    for inv in invoice_qs:
        if not inv.customer_id:
            continue
        row = by_customer[inv.customer_id]
        row['customer_name'] = inv.customer.name
        row['invoiced_total'] += inv.total_amount or Decimal('0.00')
        row['invoice_count'] += 1

    for pay in payment_qs:
        if pay.party_type != 'customer':
            continue
        cid = pay.party_id
        row = by_customer[cid]
        if not row['customer_name']:
            row['customer_name'] = pay.party_name or '—'
        row['collected_total'] += pay.amount or Decimal('0.00')

    for adv in receipt_qs:
        if not adv.customer_id:
            continue
        row = by_customer[adv.customer_id]
        if not row['customer_name']:
            row['customer_name'] = adv.customer.name
        row['collected_total'] += adv.total_amount or Decimal('0.00')

    rows = list(by_customer.values())
    rows.sort(key=lambda r: r['invoiced_total'], reverse=True)
    return rows[:100]


def _build_salesperson_performance(*, start_date, end_date, selected_salesperson=''):
    rows = []
    entries = [
        {'id': emp.pk, 'label': salesperson_display_name(emp), 'key': str(emp.pk)}
        for emp in get_sales_employee_queryset()
    ]
    entries.append({'id': None, 'label': 'Unassigned', 'key': 'none'})

    for entry in entries:
        sp_key = entry['key']
        invoiced = _money_agg(_period_invoices(start_date, end_date, sp_key))
        collected = _collected_totals(start_date, end_date, sp_key)
        won = _money_agg(
            _period_estimates(start_date, end_date, sp_key).filter(status='quotation_won')
        )
        rows.append({
            'id': entry['id'],
            'label': entry['label'],
            'filter_key': sp_key,
            'invoiced_total': invoiced['total'] or Decimal('0.00'),
            'invoiced_count': invoiced['count'] or 0,
            'collected_total': collected['total'],
            'collected_count': collected['count'],
            'won_total': won['total'] or Decimal('0.00'),
            'won_count': won['count'] or 0,
            'is_selected': selected_salesperson == sp_key,
        })

    rows.sort(key=lambda r: (r['collected_total'], r['invoiced_total']), reverse=True)
    active_rows = [
        row for row in rows
        if row['collected_total'] > 0 or row['invoiced_total'] > 0 or row['won_total'] > 0
    ]
    if selected_salesperson:
        selected_row = next((row for row in rows if row['filter_key'] == selected_salesperson), None)
        if selected_row and selected_row not in active_rows:
            active_rows.append(selected_row)
    return active_rows or rows[:1]


def _build_sales_alerts(
    *,
    start_date,
    end_date,
    salesperson,
    invoiced_total,
    collected_total,
    outstanding_count,
    outstanding_total,
):
    today = timezone.localdate()
    alerts = []

    overdue_qs = (
        Invoice.objects.filter(
            is_active=True,
            due_date__lt=today,
            status__in=INVOICE_REVENUE_STATUSES,
        )
        .annotate(balance=F('total_amount') - F('paid_amount'))
        .filter(balance__gt=Decimal('0.00'))
        .filter(invoice_salesperson_q(salesperson))
    )
    overdue_agg = overdue_qs.aggregate(
        count=Count('id'),
        total=Coalesce(Sum('balance'), Decimal('0.00')),
    )
    if overdue_agg['count']:
        alerts.append({
            'level': 'danger',
            'icon': 'fa-exclamation-circle',
            'message': (
                f'{overdue_agg["count"]} overdue invoice(s) totalling '
                f'AED {overdue_agg["total"]:,.2f} need follow-up.'
            ),
        })

    invoiced_estimate = Exists(
        Invoice.objects.filter(
            estimate_id=OuterRef('pk'),
            is_active=True,
            status__in=INVOICE_REVENUE_STATUSES,
        )
    )
    won_not_invoiced = (
        _period_estimates(start_date, end_date, salesperson)
        .filter(status='quotation_won')
        .annotate(has_invoice=invoiced_estimate)
        .filter(has_invoice=False)
    )
    won_pending_count = won_not_invoiced.count()
    if won_pending_count:
        alerts.append({
            'level': 'warning',
            'icon': 'fa-file-invoice',
            'message': (
                f'{won_pending_count} won quotation(s) in this period are not invoiced yet.'
            ),
        })

    unassigned_invoices = _period_invoices(start_date, end_date, 'none').count()
    unassigned_quotes = _period_estimates(start_date, end_date, 'none').count()
    if unassigned_invoices or unassigned_quotes:
        parts = []
        if unassigned_invoices:
            parts.append(f'{unassigned_invoices} invoice(s)')
        if unassigned_quotes:
            parts.append(f'{unassigned_quotes} quotation(s)')
        alerts.append({
            'level': 'info',
            'icon': 'fa-user-slash',
            'message': (
                f'{" and ".join(parts)} in this period have no salesman '
                f'(set Assigned to on quotations or customer salesman).'
            ),
        })

    if invoiced_total > 0 and collected_total <= 0:
        alerts.append({
            'level': 'warning',
            'icon': 'fa-hand-holding-usd',
            'message': (
                f'AED {invoiced_total:,.2f} invoiced in this period but no collections recorded yet.'
            ),
        })
    elif invoiced_total > 0:
        pct = _pct(collected_total, invoiced_total)
        if pct < 40:
            alerts.append({
                'level': 'warning',
                'icon': 'fa-chart-line',
                'message': (
                    f'Collection rate is {pct}% of invoiced amount '
                    f'(AED {collected_total:,.2f} collected vs AED {invoiced_total:,.2f} invoiced).'
                ),
            })

    if outstanding_count and outstanding_total > Decimal('5000.00'):
        alerts.append({
            'level': 'warning',
            'icon': 'fa-clock',
            'message': (
                f'Outstanding receivables: AED {outstanding_total:,.2f} '
                f'across {outstanding_count} open invoice(s).'
            ),
        })

    return alerts


def build_sales_report(*, start_date, end_date, salesperson=''):
    """Period sales report aligned with typical ERP sales dashboards."""
    salesperson = (salesperson or '').strip()
    zero = Decimal('0.00')

    invoice_qs = _period_invoices(start_date, end_date, salesperson)
    invoiced = _money_agg(invoice_qs)
    invoiced_paid = invoice_qs.aggregate(
        paid=Coalesce(Sum('paid_amount'), zero),
    )['paid'] or zero

    outstanding_qs = (
        Invoice.objects.filter(
            is_active=True,
            invoice_date__lte=end_date,
            status__in=INVOICE_REVENUE_STATUSES,
        )
        .filter(invoice_salesperson_q(salesperson))
        .annotate(
            outstanding_balance=ExpressionWrapper(
                F('total_amount') - F('paid_amount'),
                output_field=DecimalField(max_digits=15, decimal_places=2),
            ),
        )
        .filter(outstanding_balance__gt=zero)
        .select_related('customer', 'estimate', 'estimate__assigned_to')
        .order_by('-invoice_date', '-id')
    )
    outstanding_agg = outstanding_qs.aggregate(
        count=Count('id'),
        total=Coalesce(Sum('outstanding_balance'), zero),
    )

    payment_qs = _period_payments(start_date, end_date, salesperson)
    payments_agg = payment_qs.aggregate(
        count=Count('id'),
        total=Coalesce(Sum('amount'), zero),
    )

    receipt_qs = _period_receipts(start_date, end_date, salesperson)
    receipts_agg = _money_agg(
        receipt_qs,
        subtotal_field='amount',
        vat_field='vat_amount',
        total_field='total_amount',
    )

    collected_total = (payments_agg['total'] or zero) + (receipts_agg['total'] or zero)
    collected_count = (payments_agg['count'] or 0) + (receipts_agg['count'] or 0)

    credit_qs = SalesCreditNote.objects.filter(
        is_active=True,
        status='posted',
        date__gte=start_date,
        date__lte=end_date,
    ).filter(customer_salesperson_q(salesperson, prefix='customer__'))
    credit_notes = _money_agg(credit_qs)

    estimate_base = _period_estimates(start_date, end_date, salesperson)
    pipeline_rows = []
    for status_code, label in Estimate.STATUS_CHOICES:
        qs = estimate_base.filter(status=status_code)
        agg = _money_agg(qs)
        pipeline_rows.append({
            'status': status_code,
            'label': label,
            'count': agg['count'] or 0,
            'total': agg['total'] or zero,
        })

    won_qs = estimate_base.filter(status='quotation_won').select_related(
        'customer', 'assigned_to', 'customer__assigned_salesperson'
    )
    lost_qs = estimate_base.filter(status='quotation_lost').select_related(
        'customer', 'assigned_to', 'customer__assigned_salesperson'
    )
    won = _money_agg(won_qs)
    lost = _money_agg(lost_qs)

    pipeline_max = max([row['count'] for row in pipeline_rows] + [1])

    quotation_rows = [
        {
            'pk': est.pk,
            'display_estimate_number': est.display_estimate_number,
            'customer_name': est.customer.name if est.customer_id else '',
            'salesman_name': estimate_salesperson_label(est),
            'date': est.date,
            'total_amount': est.total_amount,
            'status': est.get_status_display(),
            'status_code': est.status,
        }
        for est in estimate_base.select_related(
            'customer', 'assigned_to', 'customer__assigned_salesperson'
        ).order_by('-date', '-id')[:500]
    ]

    invoiced_total = invoiced['total'] or zero

    salespeople = [
        {'id': emp.pk, 'label': salesperson_display_name(emp)}
        for emp in get_sales_employee_queryset()
    ]

    salesperson_performance = _build_salesperson_performance(
        start_date=start_date,
        end_date=end_date,
        selected_salesperson=salesperson,
    )

    today = timezone.localdate()
    is_current_month = (
        start_date.day == 1
        and start_date.month == today.month
        and start_date.year == today.year
        and end_date >= today
    )

    sales_alerts = _build_sales_alerts(
        start_date=start_date,
        end_date=end_date,
        salesperson=salesperson,
        invoiced_total=invoiced_total,
        collected_total=collected_total,
        outstanding_count=outstanding_agg['count'] or 0,
        outstanding_total=outstanding_agg['total'] or zero,
    )

    selected_performance = next(
        (row for row in salesperson_performance if row['is_selected']),
        None,
    )

    revenue_by_customer = _build_revenue_by_customer(
        invoice_qs=invoice_qs,
        payment_qs=payment_qs,
        receipt_qs=receipt_qs,
    )

    return {
        'start_date': start_date,
        'end_date': end_date,
        'filter_salesperson': salesperson,
        'filter_salespeople': salespeople,
        'is_current_month': is_current_month,
        'salesperson_performance': salesperson_performance,
        'selected_salesperson_performance': selected_performance,
        'revenue_by_customer': revenue_by_customer,
        'sales_alerts': sales_alerts,
        'invoiced': invoiced,
        'invoiced_paid': invoiced_paid,
        'outstanding': outstanding_agg,
        'payments': payments_agg,
        'receipts': receipts_agg,
        'collected': {
            'count': collected_count,
            'total': collected_total,
        },
        'credit_notes': credit_notes,
        'won': won,
        'lost': lost,
        'pipeline_rows': pipeline_rows,
        'pipeline_max_count': pipeline_max,
        'quotation_rows': quotation_rows,
        'collection_pct': _pct(collected_total, invoiced_total),
        'invoice_collection_pct': _pct(invoiced_paid, invoiced_total),
        'invoice_rows': [
            {
                'pk': inv.pk,
                'invoice_number': inv.invoice_number,
                'customer_name': inv.customer.name if inv.customer_id else '',
                'salesman_name': invoice_salesperson_label(inv),
                'date': inv.invoice_date,
                'status': inv.get_status_display(),
                'subtotal': inv.subtotal,
                'vat_amount': inv.vat_amount,
                'total_amount': inv.total_amount,
                'paid_amount': inv.paid_amount,
                'balance': inv.balance,
            }
            for inv in invoice_qs[:500]
        ],
        'outstanding_rows': [
            {
                'pk': inv.pk,
                'invoice_number': inv.invoice_number,
                'customer_name': inv.customer.name if inv.customer_id else '',
                'salesman_name': invoice_salesperson_label(inv),
                'date': inv.invoice_date,
                'due_date': inv.due_date,
                'total_amount': inv.total_amount,
                'paid_amount': inv.paid_amount,
                'balance': inv.balance,
            }
            for inv in outstanding_qs[:500]
        ],
        'won_rows': [
            {
                'pk': est.pk,
                'display_estimate_number': est.display_estimate_number,
                'customer_name': est.customer.name if est.customer_id else '',
                'salesman_name': estimate_salesperson_label(est),
                'date': est.date,
                'total_amount': est.total_amount,
            }
            for est in won_qs[:500]
        ],
        'lost_rows': [
            {
                'pk': est.pk,
                'display_estimate_number': est.display_estimate_number,
                'customer_name': est.customer.name if est.customer_id else '',
                'salesman_name': estimate_salesperson_label(est),
                'date': est.date,
                'total_amount': est.total_amount,
            }
            for est in lost_qs[:500]
        ],
        'payment_rows': [
            {
                'pk': pay.pk,
                'payment_number': pay.payment_number,
                'party_name': pay.party_name,
                'date': pay.payment_date,
                'amount': pay.amount,
                'reference': pay.reference,
                'method': pay.get_payment_method_display(),
            }
            for pay in payment_qs[:500]
        ],
        'receipt_rows': [
            {
                'pk': adv.pk,
                'advance_number': adv.advance_number,
                'customer_name': adv.customer.name if adv.customer_id else '',
                'date': adv.date,
                'total_amount': adv.total_amount,
            }
            for adv in receipt_qs[:500]
        ],
    }
