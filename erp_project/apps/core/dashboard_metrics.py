"""Clickable metric cards for the dashboard."""

from __future__ import annotations

from django.urls import NoReverseMatch, reverse

from apps.core.utils import PermissionChecker


def _can(user, module: str, perm: str = 'view') -> bool:
    return user.is_superuser or PermissionChecker.has_permission(user, module, perm)


def build_dashboard_metric_cards(user, context: dict) -> list[dict]:
    cards: list[dict] = []

    def add(*, label, value, hint, path, accent: str = 'dark', module: str | None = None):
        if module and not _can(user, module):
            return
        cards.append({
            'label': label,
            'value': value,
            'hint': hint,
            'path': path,
            'accent': accent,
        })

    try:
        if _can(user, 'sales'):
            add(
                label='Open quotations',
                value=context.get('estimates_open', 0),
                hint=f"{context.get('estimates_approved', 0)} approved / won",
                path=reverse('sales:estimate_list'),
                accent='primary',
            )
            add(
                label='Unpaid invoices',
                value=context.get('invoices_unpaid', 0),
                hint='Outstanding balance',
                path=reverse('sales:invoice_list') + '?status=outstanding',
                accent='danger',
            )
            month_label = context.get('dashboard_month_label', '')
            add(
                label=f'Invoiced · {month_label}',
                value=f"AED {context.get('invoiced_month_total', 0):,.0f}",
                hint=f"{context.get('invoiced_month_count', 0)} this month",
                path=reverse('sales:invoice_list'),
                accent='info',
            )
            add(
                label='Quotations sent',
                value=context.get('estimates_sent_pending', 0),
                hint='Awaiting customer / approval',
                path=reverse('sales:estimate_list') + '?tab=pending',
                accent='warning',
            )
    except NoReverseMatch:
        pass

    pending_count = len(context.get('dashboard_pending_items') or [])
    add(
        label='Pending approvals',
        value=pending_count,
        hint='Waiting on you',
        path='#dash-pending-work',
        accent='warning' if pending_count else 'secondary',
    )

    unread = context.get('unread_notification_count') or 0
    add(
        label='Unread notifications',
        value=unread,
        hint='In-app alerts',
        path='#dash-notifications',
        accent='warning' if unread else 'secondary',
    )

    alert_total = context.get('dashboard_alert_total') or 0
    if alert_total:
        add(
            label='Compliance alerts',
            value=alert_total,
            hint='Expiry & renewals',
            path='#dash-compliance-alerts',
            accent='danger',
        )

    try:
        if _can(user, 'projects'):
            add(
                label='Projects in progress',
                value=context.get('project_in_progress', 0),
                hint=f"{context.get('project_total', 0)} total · {context.get('contracts_active', 0)} contracts",
                path=reverse('projects:project_list'),
                accent='primary',
            )
    except NoReverseMatch:
        pass

    try:
        if _can(user, 'purchase'):
            add(
                label='Pending purchase requests',
                value=context.get('purchase_requests_pending', 0),
                hint='Awaiting approval',
                path=reverse('purchase:pr_list') + '?status=pending',
                accent='warning',
            )
            add(
                label='Expense claims',
                value=context.get('expense_claims_pending', 0),
                hint='Submitted, not approved',
                path=reverse('purchase:expenseclaim_list') + '?status=submitted',
                accent='info',
            )
    except NoReverseMatch:
        pass

    return cards
