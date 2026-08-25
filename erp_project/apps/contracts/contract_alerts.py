"""Contract renewal reminder alerts for dashboard and list views."""
from __future__ import annotations

from datetime import date
from typing import Any

from apps.core.utils import PermissionChecker


def _severity_labels(days_left: int) -> tuple[str, str]:
    if days_left < 0:
        severity = 'expired'
        ago = abs(days_left)
        label = f'Ended {ago} day ago' if ago == 1 else f'Ended {ago} days ago'
    elif days_left == 0:
        severity = 'due_today'
        label = 'Ends today'
    else:
        severity = 'reminder'
        label = f'{days_left} days left' if days_left != 1 else '1 day left'
    return severity, label


def get_contract_dashboard_alerts(user, today: date | None = None, limit: int = 20) -> list[dict[str, Any]]:
    from apps.contracts.models import Contract

    today = today or date.today()
    if not user.is_superuser and not PermissionChecker.has_permission(user, 'contracts', 'view'):
        return []

    rows: list[dict[str, Any]] = []
    qs = (
        Contract.objects.filter(is_active=True)
        .exclude(status__in=('expired', 'terminated', 'draft'))
        .select_related('customer')
        .prefetch_related('contract_types')
        .order_by('end_date')
    )
    for contract in qs:
        if not contract.reminder_due():
            continue
        days_left = (contract.end_date - today).days
        severity, label = _severity_labels(days_left)
        type_names = ', '.join(t.name for t in contract.contract_types.all()[:3])
        rows.append(
            {
                'contract': contract,
                'contract_number': contract.contract_number,
                'name': contract.name,
                'customer_name': contract.customer.name if contract.customer_id else '—',
                'end_date': contract.end_date,
                'remind_before_days': contract.remind_before_days,
                'days_left': days_left,
                'severity': severity,
                'label': label,
                'type_names': type_names,
            }
        )
        if len(rows) >= limit:
            break
    return rows


def count_reminder_due_contracts(today: date | None = None) -> int:
    from apps.contracts.models import Contract

    today = today or date.today()
    count = 0
    qs = Contract.objects.filter(is_active=True).exclude(
        status__in=('expired', 'terminated', 'draft')
    ).only('end_date', 'remind_before_days', 'status')
    for contract in qs:
        if contract.reminder_due():
            count += 1
    return count
