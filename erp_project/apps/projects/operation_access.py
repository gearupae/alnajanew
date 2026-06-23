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


def project_has_customer_advance(project) -> bool:
    """True when any active customer advance is linked to this project."""
    if not project:
        return False
    from apps.advances.models import CustomerAdvance

    return CustomerAdvance.objects.filter(
        project_id=project.pk,
        is_active=True,
    ).exists()


def project_access_unlocked(project) -> bool:
    """
    Quotation-sourced projects become fully accessible when:
    - a linked sales invoice is paid, or
    - operation update access was approved, or
    - a customer advance was recorded against the project.
    """
    if not project:
        return False
    if project_has_paid_invoice(project):
        return True
    if getattr(project, 'operation_access_status', 'none') == 'approved':
        return True
    if project_has_customer_advance(project):
        return True
    return False


def project_operations_locked(project) -> bool:
    """
    Estimate-sourced projects are read-only on the detail page until unlocked
    (paid invoice, approved operation access, or customer advance on project).
    """
    if not project or not project_created_from_estimate(project):
        return False
    from .conversion_approval import project_awaiting_conversion_approval

    if project_awaiting_conversion_approval(project):
        return True
    return not project_access_unlocked(project)


def operation_access_approval_configured() -> bool:
    return ApprovalConfiguration.objects.filter(
        module='project_operation_access', is_active=True
    ).exists()


def queue_project_operation_access_request(user, project):
    project.operation_access_status = 'pending'
    project.operation_access_submitted_at = timezone.now()
    project.operation_access_submitted_by = user
    project.operation_access_rejection_reason = ''
    project.save(
        update_fields=[
            'operation_access_status',
            'operation_access_submitted_at',
            'operation_access_submitted_by',
            'operation_access_rejection_reason',
            'updated_at',
        ]
    )
    from .project_approval_notifications import notify_approver_project_operation_access_pending

    notify_approver_project_operation_access_pending(project)


def approve_project_operation_access(project):
    project.operation_access_status = 'approved'
    project.operation_access_rejection_reason = ''
    project.save(
        update_fields=['operation_access_status', 'operation_access_rejection_reason', 'updated_at']
    )


def reject_project_operation_access(project, comment: str = ''):
    project.operation_access_status = 'rejected'
    project.operation_access_rejection_reason = (comment or '').strip()[:2000]
    project.save(
        update_fields=['operation_access_status', 'operation_access_rejection_reason', 'updated_at']
    )
