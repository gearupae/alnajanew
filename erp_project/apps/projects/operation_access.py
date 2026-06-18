"""Lock estimate-sourced project operations until paid invoice or approver grants access."""
from __future__ import annotations

from django.db.models import F, Q
from django.utils import timezone

from apps.settings_app.models import ApprovalConfiguration


def project_created_from_estimate(project) -> bool:
    return project.estimates.filter(is_active=True).exists()


def project_has_paid_invoice(project) -> bool:
    """True when a linked sales invoice is fully paid."""
    from apps.sales.models import Invoice

    invoice_ids = project.invoices.filter(is_active=True).values_list('invoice_id', flat=True)
    if not invoice_ids:
        return False
    return Invoice.objects.filter(
        pk__in=invoice_ids,
        is_active=True,
    ).filter(
        Q(status='paid')
        | Q(paid_amount__gte=F('total_amount'), total_amount__gt=0)
    ).exists()


def project_operations_locked(project) -> bool:
    """
    Estimate-sourced projects are read-only on the detail page until:
    - a linked invoice is paid, or
    - an approver grants operation access.
    """
    if not project or not project_created_from_estimate(project):
        return False
    from .conversion_approval import project_awaiting_conversion_approval

    if project_awaiting_conversion_approval(project):
        return True
    if project_has_paid_invoice(project):
        return False
    if getattr(project, 'operation_access_status', 'none') == 'approved':
        return False
    return True


def operation_access_approval_configured() -> bool:
    return ApprovalConfiguration.objects.filter(
        module='project_operation_access', is_active=True
    ).exists()


def queue_project_operation_access_request(user, project):
    project.operation_access_status = 'pending'
    project.operation_access_submitted_at = timezone.now()
    project.operation_access_submitted_by = user
    project.save(
        update_fields=[
            'operation_access_status',
            'operation_access_submitted_at',
            'operation_access_submitted_by',
            'updated_at',
        ]
    )
    from .project_approval_notifications import notify_approver_project_operation_access_pending

    notify_approver_project_operation_access_pending(project)


def approve_project_operation_access(project):
    project.operation_access_status = 'approved'
    project.save(update_fields=['operation_access_status', 'updated_at'])


def reject_project_operation_access(project):
    project.operation_access_status = 'rejected'
    project.save(update_fields=['operation_access_status', 'updated_at'])
