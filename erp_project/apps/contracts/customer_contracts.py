"""Customer-linked contract helpers for CRM detail pages."""
from __future__ import annotations

from urllib.parse import quote

from django.urls import reverse

from apps.core.utils import PermissionChecker


def customer_contracts_context(user, customer) -> dict:
    from apps.contracts.models import Contract

    contracts = (
        Contract.objects.filter(is_active=True, customer=customer)
        .prefetch_related('contract_types')
        .order_by('-start_date', '-created_at')
    )
    reminder_due = sum(
        1
        for c in contracts
        if c.reminder_due() and c.status not in ('expired', 'terminated', 'draft')
    )
    customer_name = (customer.company or customer.name or '').strip()
    create_url = reverse('contracts:contract_list')
    if customer.pk:
        create_url = f'{create_url}?customer={customer.pk}&customer_name={quote(customer_name)}'

    return {
        'customer_contracts': contracts,
        'customer_contracts_reminder_due': reminder_due,
        'can_view_contracts': user.is_superuser
        or PermissionChecker.has_permission(user, 'contracts', 'view'),
        'can_create_contract': user.is_superuser
        or PermissionChecker.has_permission(user, 'contracts', 'create'),
        'contract_create_url': create_url,
    }
