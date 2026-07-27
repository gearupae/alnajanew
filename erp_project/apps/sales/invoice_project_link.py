"""Link sales invoices to projects for revenue tracking."""
from __future__ import annotations

from apps.projects.models import Project, ProjectInvoice


def get_invoice_project(invoice):
    """Return the active project linked to this invoice, if any."""
    if not invoice or not invoice.pk:
        return None
    link = (
        invoice.project_links.filter(is_active=True)
        .select_related('project')
        .order_by('-pk')
        .first()
    )
    return link.project if link else None


def save_invoice_project_link(invoice, project: Project | None) -> None:
    """Set or clear the project linked to an invoice."""
    active_links = list(
        ProjectInvoice.objects.filter(invoice=invoice, is_active=True).select_related('project')
    )
    if not project:
        for link in active_links:
            link.is_active = False
            link.save(update_fields=['is_active'])
        return

    for link in active_links:
        if link.project_id == project.pk:
            return
        link.is_active = False
        link.save(update_fields=['is_active'])

    ProjectInvoice.objects.create(project=project, invoice=invoice)

    from apps.projects.operation_access import maybe_auto_approve_project_financial_unlock

    maybe_auto_approve_project_financial_unlock(project)
