"""Pending work and important alerts for the home dashboard."""

from __future__ import annotations

from django.urls import reverse

from apps.settings_app.models import Notification


def _item(*, kind: str, title: str, detail: str, path: str, request, severity: str = 'warning') -> dict:
    return {
        'kind': kind,
        'title': title,
        'detail': detail,
        'path': path,
        'url': request.build_absolute_uri(path),
        'severity': severity,
    }


def dashboard_important_notifications(user, *, limit: int = 8) -> list[dict]:
    if not user or not user.is_authenticated:
        return []
    rows = []
    for n in Notification.objects.filter(user=user, is_read=False).order_by('-created_at')[:limit]:
        link = (n.link or '').strip() or '/'
        if not link.startswith('/') or link.startswith('//'):
            link = '/'
        rows.append(
            {
                'pk': n.pk,
                'title': n.title,
                'message': n.message,
                'created_at': n.created_at,
                'path': link,
                'open_url': reverse('notification_open', kwargs={'pk': n.pk}),
            }
        )
    return rows


def dashboard_pending_work(user, request) -> list[dict]:
    """Actionable items for the current user (approvals, reviews, drafts)."""
    if not user or not user.is_authenticated:
        return []
    items: list[dict] = []

    try:
        from apps.purchase.pr_approval_rules import pending_purchase_requests_for_user

        for pr in pending_purchase_requests_for_user(user)[:12]:
            items.append(
                _item(
                    kind='purchase_request',
                    title=f'Approve purchase request {pr.pr_number}',
                    detail=pr.requested_by.get_full_name() if pr.requested_by else 'Purchase request',
                    path=reverse('purchase:pr_detail', kwargs={'pk': pr.pk}),
                    request=request,
                    severity='danger',
                )
            )
    except Exception:
        pass

    try:
        from apps.inventory.inventory_approval_rules import pending_items_for_user, pending_adjustments_for_user

        for item in pending_items_for_user(user)[:8]:
            items.append(
                _item(
                    kind='inventory_item',
                    title=f'Review item {item.code}',
                    detail=item.name,
                    path=reverse('inventory:item_detail', kwargs={'pk': item.pk}),
                    request=request,
                )
            )
        for adj in pending_adjustments_for_user(user)[:8]:
            items.append(
                _item(
                    kind='inventory_adjustment',
                    title=f'Approve stock adjustment {adj.reference or adj.pk}',
                    detail=getattr(adj, 'reason', '') or 'Inventory adjustment',
                    path=reverse('inventory:movement_detail', kwargs={'pk': adj.pk}),
                    request=request,
                )
            )
    except Exception:
        pass

    try:
        from apps.projects.approval_rules import (
            pending_completion_projects_for_user,
            pending_conversion_projects_for_user,
            pending_operation_access_projects_for_user,
        )

        for project in pending_completion_projects_for_user(user)[:8]:
            items.append(
                _item(
                    kind='project_completion',
                    title=f'Completion review · {project.project_code}',
                    detail=project.name,
                    path=reverse('projects:project_detail', kwargs={'pk': project.pk}),
                    request=request,
                    severity='danger',
                )
            )
        for project in pending_conversion_projects_for_user(user)[:8]:
            items.append(
                _item(
                    kind='project_conversion',
                    title=f'Estimate conversion · {project.project_code}',
                    detail=project.name,
                    path=reverse('projects:project_detail', kwargs={'pk': project.pk}),
                    request=request,
                )
            )
        for project in pending_operation_access_projects_for_user(user)[:8]:
            items.append(
                _item(
                    kind='project_access',
                    title=f'Operation access · {project.project_code}',
                    detail=project.name,
                    path=reverse('projects:project_detail', kwargs={'pk': project.pk}),
                    request=request,
                )
            )
    except Exception:
        pass

    try:
        from apps.sales.models import Estimate
        from apps.core.approval_visibility import estimate_approver_records_q

        if user.is_superuser:
            est_qs = Estimate.objects.filter(is_active=True, status='sent')
        else:
            est_qs = Estimate.objects.filter(is_active=True).filter(estimate_approver_records_q(user)).filter(
                status='sent'
            )
        for est in est_qs.select_related('customer')[:8]:
            items.append(
                _item(
                    kind='estimate',
                    title=f'Quotation awaiting action · {est.display_estimate_number}',
                    detail=est.customer.name if est.customer_id else est.document_title or 'Estimate',
                    path=reverse('sales:estimate_detail', kwargs={'pk': est.pk}),
                    request=request,
                )
            )
        edit_qs = Estimate.objects.filter(is_active=True, edit_approval_status='pending')
        if not user.is_superuser:
            edit_qs = edit_qs.filter(estimate_approver_records_q(user))
        for est in edit_qs.select_related('customer')[:8]:
            items.append(
                _item(
                    kind='estimate_edit',
                    title=f'Quotation edit pending · {est.display_estimate_number}',
                    detail=est.customer.name if est.customer_id else 'Edit approval',
                    path=reverse('sales:estimate_detail', kwargs={'pk': est.pk}),
                    request=request,
                    severity='danger',
                )
            )
    except Exception:
        pass

    try:
        from apps.hr.leave_approval_rules import user_can_act_on_leave_request
        from apps.hr.models import LeaveRequest

        leave_qs = LeaveRequest.objects.filter(
            status__in=['pending_manager', 'pending_hr'],
            is_active=True,
        ).select_related('employee')
        for leave in leave_qs.order_by('-created_at')[:30]:
            if not user.is_superuser and not user_can_act_on_leave_request(user, leave):
                continue
            items.append(
                _item(
                    kind='leave',
                    title='Leave request pending approval',
                    detail=str(leave.employee),
                    path=reverse('hr:leave_detail', kwargs={'pk': leave.pk}),
                    request=request,
                    severity='danger',
                )
            )
            if sum(1 for i in items if i['kind'] == 'leave') >= 8:
                break
    except Exception:
        pass

    try:
        from apps.purchase.models import ExpenseClaim

        claims = ExpenseClaim.objects.filter(is_active=True, status='submitted').select_related('employee')[:8]
        for claim in claims:
            items.append(
                _item(
                    kind='expense',
                    title=f'Expense claim {claim.claim_number}',
                    detail=claim.employee.get_full_name() if claim.employee else 'Submitted',
                    path=reverse('purchase:expenseclaim_detail', kwargs={'pk': claim.pk}),
                    request=request,
                )
            )
    except Exception:
        pass

    severity_order = {'danger': 0, 'warning': 1, 'info': 2}
    items.sort(key=lambda x: (severity_order.get(x['severity'], 9), x['title']))
    return items[:25]
