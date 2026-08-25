"""Compliance document expiry alerts for the main dashboard."""
from __future__ import annotations

from datetime import date
from typing import Any

from apps.core.utils import PermissionChecker


def _severity_labels(days_left: int) -> tuple[str, str]:
    if days_left < 0:
        severity = 'expired'
        ago = abs(days_left)
        label = f'Expired {ago} day ago' if ago == 1 else f'Expired {ago} days ago'
    elif days_left == 0:
        severity = 'due_today'
        label = 'Expires today'
    else:
        severity = 'expiring'
        label = f'{days_left} days left' if days_left != 1 else '1 day left'
    return severity, label


def get_documents_dashboard_alerts(user, today: date | None = None, limit: int = 20) -> list[dict[str, Any]]:
    from apps.documents.document_utils import document_status
    from apps.documents.models import Document

    today = today or date.today()
    if not user.is_superuser and not PermissionChecker.has_permission(user, 'documents', 'view'):
        return []

    rows: list[dict[str, Any]] = []
    qs = Document.objects.filter(is_active=True).select_related('document_type').order_by('expiry_date')
    for doc in qs:
        status = document_status(doc, today)
        if status not in ('expired', 'expiring'):
            continue
        days_left = (doc.expiry_date - today).days
        severity, label = _severity_labels(days_left)
        rows.append(
            {
                'document': doc,
                'document_type': doc.document_type.name,
                'entity_type': doc.get_entity_type_display(),
                'entity_name': doc.entity_name,
                'expiry_date': doc.expiry_date,
                'days_left': days_left,
                'severity': severity,
                'label': label,
                'alert_days': doc.document_type.alert_days_before,
            }
        )
        if len(rows) >= limit:
            break
    return rows
