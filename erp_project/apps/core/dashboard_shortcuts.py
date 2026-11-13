"""Permission-filtered quick links for the home dashboard."""

from __future__ import annotations

from django.urls import NoReverseMatch, reverse

from apps.core.utils import PermissionChecker


def _can(user, module: str, perm: str = 'view') -> bool:
    return user.is_superuser or PermissionChecker.has_permission(user, module, perm)


def dashboard_shortcuts(user, request) -> list[dict]:
    specs = [
        {'title': 'New quotation', 'icon': 'fa-file-signature', 'tone': 'warning', 'module': 'sales', 'perm': 'create', 'url_name': 'sales:estimate_create'},
        {'title': 'Quotations', 'icon': 'fa-file-invoice', 'tone': 'primary', 'module': 'sales', 'url_name': 'sales:estimate_list'},
        {'title': 'Invoices', 'icon': 'fa-receipt', 'tone': 'info', 'module': 'sales', 'url_name': 'sales:invoice_list'},
        {'title': 'Customers', 'icon': 'fa-users', 'tone': 'secondary', 'module': 'crm', 'url_name': 'crm:customer_list'},
        {'title': 'Projects', 'icon': 'fa-project-diagram', 'tone': 'primary', 'module': 'projects', 'url_name': 'projects:project_list'},
        {'title': 'Purchase orders', 'icon': 'fa-shopping-bag', 'tone': 'success', 'module': 'purchase', 'url_name': 'purchase:po_list'},
        {'title': 'Inventory', 'icon': 'fa-boxes', 'tone': 'dark', 'module': 'inventory', 'url_name': 'inventory:item_list'},
        {'title': 'Payments', 'icon': 'fa-money-bill-wave', 'tone': 'success', 'module': 'finance', 'url_name': 'finance:payment_list'},
        {'title': 'Employees', 'icon': 'fa-user-tie', 'tone': 'secondary', 'module': 'hr', 'url_name': 'hr:employee_list'},
        {'title': 'Attendance', 'icon': 'fa-clock', 'tone': 'info', 'module': 'hr', 'url_name': 'hr:attendance_list'},
        {'title': 'Contracts', 'icon': 'fa-file-contract', 'tone': 'warning', 'module': 'contracts', 'url_name': 'contracts:contract_list'},
        {'title': 'Reports', 'icon': 'fa-chart-bar', 'tone': 'dark', 'module': 'reports', 'url_name': 'reports:index'},
    ]
    out: list[dict] = []
    for spec in specs:
        perm = spec.get('perm', 'view')
        if not _can(user, spec['module'], perm):
            continue
        try:
            path = reverse(spec['url_name'])
        except NoReverseMatch:
            continue
        out.append({
            'title': spec['title'],
            'icon': spec['icon'],
            'tone': spec.get('tone', 'primary'),
            'path': path,
        })
    return out
