"""Rejection detail text for project approval workflows."""
from __future__ import annotations

GENERIC_REJECT_COMMENTS = frozenset({
    'Project completion rejected',
    'Project conversion rejected',
    'Project operation access rejected',
})


def _audit_rejection_comment(project_code: str, module: str) -> str:
    from apps.settings_app.models import ApprovalAuditLog

    log = (
        ApprovalAuditLog.objects.filter(
            module=module,
            reference=project_code,
            action='reject',
        )
        .order_by('-timestamp')
        .first()
    )
    if not log:
        return ''
    comment = (log.comment or '').strip()
    if not comment or comment in GENERIC_REJECT_COMMENTS:
        return ''
    return comment


def project_completion_rejection_detail(project) -> str:
    if project.edit_approval_status != 'rejected':
        return ''
    stored = (project.edit_approval_rejection_reason or '').strip()
    if stored:
        return stored
    return _audit_rejection_comment(project.project_code, 'project')


def project_conversion_rejection_detail(project) -> str:
    if project.conversion_approval_status != 'rejected':
        return ''
    stored = (project.conversion_approval_rejection_reason or '').strip()
    if stored:
        return stored
    return _audit_rejection_comment(project.project_code, 'project_conversion')


def project_operation_access_rejection_detail(project) -> str:
    if project.operation_access_status != 'rejected':
        return ''
    stored = (project.operation_access_rejection_reason or '').strip()
    if stored:
        return stored
    return _audit_rejection_comment(project.project_code, 'project_operation_access')
