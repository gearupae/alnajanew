"""Salesman attribution helpers for the sales report."""
from __future__ import annotations

from django.db.models import Q

from apps.crm.utils import salesperson_display_name


def employee_user_id(employee_id: int):
    from apps.hr.models import Employee

    emp = Employee.objects.filter(pk=employee_id).only('user_id').first()
    return emp.user_id if emp else None


def employee_for_user(user_id):
    if not user_id:
        return None
    from apps.hr.models import Employee

    return Employee.objects.filter(user_id=user_id, is_active=True).select_related(
        'designation', 'department'
    ).first()


def estimate_salesperson_label(estimate) -> str:
    if not estimate:
        return '—'
    if estimate.assigned_to_id:
        emp = employee_for_user(estimate.assigned_to_id)
        if emp:
            return salesperson_display_name(emp)
        user = estimate.assigned_to
        return (user.get_full_name() or user.username or '—').strip() if user else '—'
    if estimate.customer_id and estimate.customer.assigned_salesperson_id:
        return salesperson_display_name(estimate.customer.assigned_salesperson)
    return '—'


def invoice_salesperson_label(invoice) -> str:
    if not invoice:
        return '—'
    if invoice.estimate_id and invoice.estimate:
        label = estimate_salesperson_label(invoice.estimate)
        if label != '—':
            return label
    if invoice.customer_id and invoice.customer.assigned_salesperson_id:
        return salesperson_display_name(invoice.customer.assigned_salesperson)
    return '—'


def estimate_salesperson_q(salesperson: str) -> Q:
    """Quotations: Assigned to is the salesman; fallback to customer assigned salesman."""
    if not salesperson:
        return Q()
    if salesperson == 'none':
        return Q(assigned_to__isnull=True, customer__assigned_salesperson__isnull=True)
    try:
        employee_id = int(salesperson)
    except (TypeError, ValueError):
        return Q()
    user_id = employee_user_id(employee_id)
    q = Q(assigned_to__isnull=True, customer__assigned_salesperson_id=employee_id)
    if user_id:
        q |= Q(assigned_to_id=user_id)
    return q


def invoice_salesperson_q(salesperson: str) -> Q:
    """Invoices from quotation: estimate Assigned to; otherwise customer salesman."""
    if not salesperson:
        return Q()
    if salesperson == 'none':
        return (
            Q(estimate__isnull=True, customer__assigned_salesperson__isnull=True)
            | Q(
                estimate__isnull=False,
                estimate__assigned_to__isnull=True,
                customer__assigned_salesperson__isnull=True,
            )
        )
    try:
        employee_id = int(salesperson)
    except (TypeError, ValueError):
        return Q()
    user_id = employee_user_id(employee_id)
    from_quote = Q(estimate__isnull=False)
    if user_id:
        from_quote &= Q(estimate__assigned_to_id=user_id)
    else:
        from_quote = Q(pk__in=[])
    no_quote = Q(estimate__isnull=True, customer__assigned_salesperson_id=employee_id)
    return from_quote | no_quote


def customer_salesperson_q(salesperson: str, *, prefix: str = '') -> Q:
    """Collections: customer salesman or any quotation Assigned to on the customer."""
    field = f'{prefix}assigned_salesperson_id'
    null_field = f'{prefix}assigned_salesperson'
    estimates_assigned = f'{prefix}estimates__assigned_to_id'
    estimates_active = f'{prefix}estimates__is_active'
    if not salesperson:
        return Q()
    if salesperson == 'none':
        return Q(**{f'{null_field}__isnull': True}) & ~Q(
            **{estimates_active: True, f'{prefix}estimates__assigned_to__isnull': False}
        )
    try:
        employee_id = int(salesperson)
    except (TypeError, ValueError):
        return Q()
    user_id = employee_user_id(employee_id)
    q = Q(**{field: employee_id})
    if user_id:
        q |= Q(**{estimates_active: True, estimates_assigned: user_id})
    return q
