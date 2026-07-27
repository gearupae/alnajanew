"""Resolve vendor bills charged to a project (direct link or via purchase order)."""
from __future__ import annotations

from decimal import Decimal

from django.db.models import Q, Sum


def vendor_bills_queryset_for_project(project):
    """
    Active vendor bills that belong to this project either via VendorBill.project
    or via VendorBill.purchase_order.project.
    """
    from apps.purchase.models import VendorBill

    return (
        VendorBill.objects.filter(is_active=True)
        .exclude(status='cancelled')
        .filter(Q(project=project) | Q(purchase_order__project=project))
        .select_related('vendor', 'purchase_order', 'project')
        .distinct()
        .order_by('-bill_date', '-pk')
    )


def vendor_bills_total_for_project(project) -> Decimal:
    return vendor_bills_queryset_for_project(project).aggregate(
        s=Sum('total_amount')
    )['s'] or Decimal('0.00')


def effective_vendor_bill_project_id(bill) -> int | None:
    if bill.project_id:
        return bill.project_id
    if bill.purchase_order_id and bill.purchase_order.project_id:
        return bill.purchase_order.project_id
    return None


def vendor_bills_totals_by_project_id(project_ids: list[int]) -> dict[int, Decimal]:
    """Batch sum vendor bill totals per project (for project list)."""
    from apps.purchase.models import VendorBill

    if not project_ids:
        return {}

    pid_set = set(project_ids)
    totals = {pid: Decimal('0.00') for pid in project_ids}
    bills = (
        VendorBill.objects.filter(is_active=True)
        .exclude(status='cancelled')
        .filter(
            Q(project_id__in=project_ids) | Q(purchase_order__project_id__in=project_ids)
        )
        .select_related('purchase_order')
    )
    for bill in bills:
        pid = effective_vendor_bill_project_id(bill)
        if pid in pid_set:
            totals[pid] += bill.total_amount or Decimal('0.00')
    return totals
