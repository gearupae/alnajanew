"""Financial and progress metrics for the projects list view."""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from django.db.models import Count, Prefetch, Q, Sum, Value
from django.db.models.fields import DecimalField
from django.db.models.functions import Coalesce

from apps.sales.models import Estimate

from .item_delivery import project_inventory_spend_total
from .labour_utils import project_labour_summary
from .models import Project
from .project_receipt_metrics import project_receipt_totals


_INVOICE_STATUS_FILTER = Q(
    invoices__is_active=True,
    invoices__invoice__is_active=True,
    invoices__invoice__status__in=['posted', 'paid', 'partial'],
)


def annotate_project_list_queryset(queryset):
    """DB annotations for list columns (expense partials, invoices, tasks)."""
    dec = DecimalField(max_digits=18, decimal_places=2)
    zero = Value(Decimal('0.00'), output_field=dec)

    queryset = queryset.annotate(
        manual_expenses_sum=Coalesce(
            Sum(
                'project_expenses__total_amount',
                filter=Q(project_expenses__is_active=True)
                & ~Q(project_expenses__status='rejected')
                & Q(project_expenses__vendor_bill__isnull=True),
            ),
            zero,
            output_field=dec,
        ),
        vendor_bills_sum=Coalesce(
            Sum(
                'vendor_bills__total_amount',
                filter=Q(vendor_bills__is_active=True) & ~Q(vendor_bills__status='cancelled'),
            ),
            zero,
            output_field=dec,
        ),
        received_amount=Coalesce(
            Sum('invoices__invoice__paid_amount', filter=_INVOICE_STATUS_FILTER),
            zero,
            output_field=dec,
        ),
        invoiced_amount=Coalesce(
            Sum('invoices__invoice__total_amount', filter=_INVOICE_STATUS_FILTER),
            zero,
            output_field=dec,
        ),
        tasks_total_count=Count('tasks', filter=Q(tasks__is_active=True), distinct=True),
        tasks_completed_count=Count(
            'tasks',
            filter=Q(tasks__is_active=True, tasks__status='completed'),
            distinct=True,
        ),
    )
    return queryset


def _estimated_expense_by_project_id(project_ids: list[int]) -> dict[int, Decimal]:
    if not project_ids:
        return {}

    from apps.sales.models import EstimateItem

    estimate_qs = Estimate.objects.filter(
        project_id__in=project_ids,
        is_active=True,
    ).prefetch_related(
        Prefetch(
            'items',
            queryset=EstimateItem.objects.select_related('inventory_item').order_by(
                'sort_order', 'id'
            ),
        ),
    )

    by_project: dict[int, list] = defaultdict(list)
    for estimate in estimate_qs:
        by_project[estimate.project_id].append(estimate)

    from apps.sales.estimate_pdf_groups import build_expense_type_base_totals_for_estimates

    totals: dict[int, Decimal] = {}
    for pid in project_ids:
        estimates = by_project.get(pid, [])
        if not estimates:
            totals[pid] = Decimal('0.00')
            continue
        rows = build_expense_type_base_totals_for_estimates(estimates)
        if rows:
            totals[pid] = sum((r['line_total'] for r in rows), Decimal('0.00'))
        else:
            totals[pid] = Decimal('0.00')
    return totals


def enrich_projects_for_list(projects: list[Project]) -> list[Project]:
    """
    Attach list_* attributes used by project_list.html.
    Call after annotate_project_list_queryset on the same project rows.
    """
    if not projects:
        return projects

    project_ids = [p.pk for p in projects]
    estimated_by_id = _estimated_expense_by_project_id(project_ids)
    from .project_vendor_bills import vendor_bills_totals_by_project_id

    bills_by_id = vendor_bills_totals_by_project_id(project_ids)

    for project in projects:
        manual = project.manual_expenses_sum or Decimal('0.00')
        bills = bills_by_id.get(project.pk, Decimal('0.00'))
        inventory = project_inventory_spend_total(project)
        _, _, labour_cost = project_labour_summary(project)
        labour_cost = labour_cost or Decimal('0.00')

        actual = manual + bills + inventory + labour_cost
        estimated = estimated_by_id.get(project.pk, Decimal('0.00'))
        if estimated <= 0 and project.budget > 0:
            estimated = project.budget

        receipt = project_receipt_totals(project)
        received = receipt['received_amount']
        invoiced = receipt['invoiced_amount']
        balance = receipt['balance_amount']
        contract = project.contract_value or Decimal('0.00')

        total_tasks = project.tasks_total_count or 0
        completed = project.tasks_completed_count or 0
        if total_tasks:
            work_pct = (
                Decimal(completed) / Decimal(total_tasks) * Decimal('100')
            ).quantize(Decimal('0.1'))
        else:
            work_pct = Decimal('0')

        project.list_contract_value = contract
        project.list_estimated_expense = estimated
        project.list_actual_expense = actual
        project.list_received_amount = received
        project.list_invoiced_amount = invoiced
        project.list_balance_amount = balance
        project.list_work_percent = work_pct

    return projects
