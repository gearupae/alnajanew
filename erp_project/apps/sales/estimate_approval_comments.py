"""Rejection detail text for estimate approval workflows."""
from __future__ import annotations


def _audit_edit_rejection_comment(estimate_number: str) -> str:
    from apps.settings_app.models import ApprovalAuditLog

    log = (
        ApprovalAuditLog.objects.filter(
            module='estimate',
            reference=estimate_number,
            action='reject',
        )
        .order_by('-timestamp')
        .first()
    )
    if not log:
        return ''
    return (log.comment or '').strip()


def estimate_edit_rejection_detail(estimate) -> str:
    if estimate.edit_approval_status != 'rejected':
        return ''
    stored = (getattr(estimate, 'edit_approval_rejection_reason', None) or '').strip()
    if stored:
        return stored
    return _audit_edit_rejection_comment(estimate.estimate_number)
