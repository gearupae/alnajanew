"""Period Wise Report: period-wise portfolio grouped by role."""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Count, Prefetch, Q

from apps.projects.member_roles import (
    all_operation_manager_users,
    all_salesmen_users,
    all_site_engineer_users,
    resolve_operation_manager_from_members,
    resolve_salesman_user,
    resolve_site_engineer_from_members,
    user_filter_options,
    user_role_label,
)
from apps.projects.models import Project
from apps.projects.project_list_metrics import annotate_project_list_queryset, enrich_projects_for_list
from apps.sales.models import Estimate

User = get_user_model()

GROUP_BY_CHOICES = [
    ('', 'All projects (flat list)'),
    ('salesman', 'Salesman wise'),
    ('site_engineer', 'Site engineer wise'),
    ('operation_manager', 'Operation manager wise'),
]


def projects_in_period(start_date, end_date):
    """Projects active or scheduled within the selected date range."""
    return Project.objects.filter(is_active=True).filter(
        Q(start_date__isnull=True, created_at__date__gte=start_date, created_at__date__lte=end_date)
        | Q(start_date__lte=end_date, end_date__gte=start_date)
        | Q(start_date__lte=end_date, end_date__isnull=True)
    )


def _base_queryset(start_date, end_date):
    estimate_qs = Estimate.objects.filter(is_active=True).select_related(
        'assigned_to',
        'assigned_to__employee_profile',
    )
    return annotate_project_list_queryset(
        projects_in_period(start_date, end_date)
        .select_related('customer', 'manager', 'manager__employee_profile')
        .prefetch_related(
            Prefetch('estimates', queryset=estimate_qs),
            'members__employee_profile__designation',
        )
        .order_by('-start_date', '-created_at', '-pk')
    )


def _project_row(project) -> dict:
    salesman_user = resolve_salesman_user(project)
    site_engineer = resolve_site_engineer_from_members(project)
    operation_manager = resolve_operation_manager_from_members(project)
    total = getattr(project, 'tasks_total_count', None) or 0
    completed = getattr(project, 'tasks_completed_count', None) or 0
    progress = Decimal('0')
    if total:
        progress = (Decimal(completed) / Decimal(total) * Decimal('100')).quantize(Decimal('0.1'))

    contract_value = getattr(project, 'list_contract_value', project.contract_value or Decimal('0'))
    estimated_expense = getattr(project, 'list_estimated_expense', Decimal('0'))
    actual_expense = getattr(project, 'list_actual_expense', Decimal('0'))
    invoiced_amount = getattr(project, 'list_invoiced_amount', Decimal('0'))
    received_amount = getattr(project, 'list_received_amount', Decimal('0'))
    balance_amount = getattr(project, 'list_balance_amount', Decimal('0'))
    gross_margin = received_amount - actual_expense

    return {
        'pk': project.pk,
        'project_code': project.project_code,
        'name': project.name,
        'customer_name': project.customer.name if project.customer_id else '—',
        'status': project.status,
        'status_display': project.get_status_display(),
        'start_date': project.start_date,
        'end_date': project.end_date,
        'salesman': salesman_user,
        'salesman_label': user_role_label(salesman_user),
        'salesman_key': salesman_user.pk if salesman_user else 0,
        'site_engineer': site_engineer,
        'site_engineer_label': user_role_label(site_engineer),
        'site_engineer_key': site_engineer.pk if site_engineer else 0,
        'operation_manager': operation_manager,
        'operation_manager_label': user_role_label(operation_manager),
        'operation_manager_key': operation_manager.pk if operation_manager else 0,
        'total_tasks': total,
        'completed_tasks': completed,
        'task_progress_percent': progress,
        'contract_value': contract_value,
        'estimated_expense': estimated_expense,
        'actual_expense': actual_expense,
        'invoiced_amount': invoiced_amount,
        'received_amount': received_amount,
        'balance_amount': balance_amount,
        'gross_margin': gross_margin,
    }


def _filter_rows(rows, *, salesman='', site_engineer='', operation_manager=''):
    if salesman == 'none':
        rows = [r for r in rows if not r['salesman']]
    elif salesman:
        try:
            pk = int(salesman)
            rows = [r for r in rows if r['salesman_key'] == pk]
        except (TypeError, ValueError):
            pass

    if site_engineer == 'none':
        rows = [r for r in rows if not r['site_engineer']]
    elif site_engineer:
        try:
            pk = int(site_engineer)
            rows = [r for r in rows if r['site_engineer_key'] == pk]
        except (TypeError, ValueError):
            pass

    if operation_manager == 'none':
        rows = [r for r in rows if not r['operation_manager']]
    elif operation_manager:
        try:
            pk = int(operation_manager)
            rows = [r for r in rows if r['operation_manager_key'] == pk]
        except (TypeError, ValueError):
            pass

    return rows


def _group_rows(rows, group_by: str):
    if not group_by:
        return []

    buckets = defaultdict(list)
    for row in rows:
        if group_by == 'salesman':
            key = row['salesman_key']
            label = row['salesman_label']
        elif group_by == 'site_engineer':
            key = row['site_engineer_key']
            label = row['site_engineer_label']
        elif group_by == 'operation_manager':
            key = row['operation_manager_key']
            label = row['operation_manager_label']
        else:
            continue
        buckets[(key, label)].append(row)

    groups = []
    for (key, label), items in buckets.items():
        groups.append(
            {
                'key': key,
                'label': label,
                'count': len(items),
                'completed_projects': sum(1 for i in items if i['status'] == 'completed'),
                'rows': items,
            }
        )
    groups.sort(key=lambda g: (g['key'] == 0, g['label'].lower()))
    return groups


def _status_summary(rows):
    summary = defaultdict(int)
    for row in rows:
        summary[row['status']] += 1
    return dict(summary)


def build_project_report_period(
    *,
    start_date,
    end_date,
    group_by='',
    status='',
    salesman='',
    site_engineer='',
    operation_manager='',
):
    qs = _base_queryset(start_date, end_date)
    if status:
        qs = qs.filter(status=status)

    projects = list(qs)
    enrich_projects_for_list(projects)
    all_rows = [_project_row(p) for p in projects]
    rows = _filter_rows(
        all_rows,
        salesman=salesman,
        site_engineer=site_engineer,
        operation_manager=operation_manager,
    )

    status_counts = _status_summary(rows)
    groups = _group_rows(rows, group_by)

    zero = Decimal('0.00')
    financial_totals = {
        'contract_value': sum((r['contract_value'] for r in rows), zero),
        'estimated_expense': sum((r['estimated_expense'] for r in rows), zero),
        'actual_expense': sum((r['actual_expense'] for r in rows), zero),
        'invoiced_amount': sum((r['invoiced_amount'] for r in rows), zero),
        'received_amount': sum((r['received_amount'] for r in rows), zero),
        'balance_amount': sum((r['balance_amount'] for r in rows), zero),
        'gross_margin': sum((r['gross_margin'] for r in rows), zero),
    }

    return {
        'start_date': start_date,
        'end_date': end_date,
        'group_by': group_by,
        'group_by_choices': GROUP_BY_CHOICES,
        'status_filter': status,
        'status_choices': Project.STATUS_CHOICES,
        'salesman_filter': salesman,
        'site_engineer_filter': site_engineer,
        'operation_manager_filter': operation_manager,
        'salesman_options': user_filter_options(all_salesmen_users()),
        'site_engineer_options': user_filter_options(all_site_engineer_users()),
        'operation_manager_options': user_filter_options(all_operation_manager_users()),
        'rows': rows,
        'groups': groups,
        'total_projects': len(rows),
        'status_counts': status_counts,
        'in_progress_count': status_counts.get('in_progress', 0),
        'completed_count': status_counts.get('completed', 0),
        'planning_count': status_counts.get('planning', 0),
        'on_hold_count': status_counts.get('on_hold', 0),
        'cancelled_count': status_counts.get('cancelled', 0),
        'financial_totals': financial_totals,
    }
