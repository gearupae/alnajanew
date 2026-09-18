"""In-app notifications when a lead enters a Site Visit pipeline stage."""
from django.urls import reverse

from apps.settings_app.models import Notification

SITE_VISIT_NOTIFICATION_TITLE = 'Site visit pending'


def _site_visit_recipients(lead, actor=None):
    users = []
    seen = set()
    emp = getattr(lead, 'assigned_salesperson', None)
    if emp and emp.user_id:
        users.append(emp.user)
        seen.add(emp.user_id)
    if actor and getattr(actor, 'is_authenticated', False) and actor.pk not in seen:
        users.append(actor)
    return users


def notify_site_visit_pending(lead, *, actor=None):
    """Notify assignee (and actor if different) that a site visit is pending."""
    if not lead or lead.customer_type != 'lead':
        return
    stage = lead.lead_kanban_stage
    if not stage or not stage.is_site_visit:
        return

    link = reverse('crm:customer_detail', args=[lead.pk])
    label = (lead.company or lead.name or '').strip() or lead.customer_number
    message = f'{lead.customer_number} — {label}. Schedule or complete the site visit.'

    for user in _site_visit_recipients(lead, actor=actor):
        already = Notification.objects.filter(
            user=user,
            title=SITE_VISIT_NOTIFICATION_TITLE,
            link=link,
            is_read=False,
        ).exists()
        if already:
            continue
        Notification.create(
            user=user,
            title=SITE_VISIT_NOTIFICATION_TITLE,
            message=message,
            link=link,
        )


def maybe_notify_site_visit_stage_change(lead, previous_stage_id, *, actor=None):
    """Call after lead_kanban_stage is saved."""
    if not lead.lead_kanban_stage_id:
        return
    if lead.lead_kanban_stage_id == previous_stage_id:
        return
    if lead.lead_kanban_stage.is_site_visit:
        notify_site_visit_pending(lead, actor=actor)
