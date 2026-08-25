"""Create a project from an approved estimate (optional line items → project Items card)."""
from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.db.models import Max

from apps.projects.models import Project, ProjectItemLine

from .models import EstimateItem


def _estimate_line_base_unit_price(line: EstimateItem) -> Decimal:
    """Base price per unit for project budget (estimate base = inventory selling price)."""
    base = line.unit_price or Decimal('0')
    if base <= 0 and line.rate and line.rate > 0:
        base = line.rate
    if base <= 0 and line.total and line.quantity and line.quantity > 0:
        base = (line.total / line.quantity).quantize(Decimal('0.01'))
    if base <= 0 and line.inventory_item_id:
        inv = line.inventory_item
        base = inv.selling_price or inv.purchase_price or Decimal('0')
    return base


def _estimate_line_display_label(line: EstimateItem) -> str:
    """Label for copied scope line — prefer inventory name, then description / group."""
    if line.inventory_item_id:
        inv = line.inventory_item
        name = (getattr(inv, 'name', None) or '').strip()
        if name:
            desc = (line.description or '').strip()
            if desc and desc.lower() != name.lower() and name.lower() not in desc.lower():
                return f'{name} — {desc}'[:500]
            return name[:500]
        fb = (getattr(inv, 'item_code', None) or str(inv).strip())[:500]
        if fb:
            return fb
    text = (line.description or '').strip()
    if text:
        return text[:500]
    group = (line.group_name or '').strip()
    if group:
        return group[:500]
    return f'Estimate line #{line.pk}'[:500]


def _next_item_line_sort_order(project) -> int:
    agg = ProjectItemLine.objects.filter(project_id=project.pk).aggregate(mx=Max('sort_order'))
    return (agg['mx'] or 0) + 1


def copy_estimate_items_to_project(*, estimate, project, sort_start: int | None = None) -> int:
    """Append estimate lines as ProjectItemLine rows. Returns count created."""
    if sort_start is None:
        sort_start = _next_item_line_sort_order(project)

    qs = (
        EstimateItem.objects.filter(estimate=estimate)
        .order_by('sort_order', 'id')
        .select_related('inventory_item')
    )
    bulk = []
    sort_order = sort_start
    for line in qs:
        bulk.append(
            ProjectItemLine(
                project=project,
                sort_order=sort_order,
                group_name=(line.group_name or '')[:200],
                description=_estimate_line_display_label(line),
                inventory_item_id=line.inventory_item_id,
                quantity=line.quantity or Decimal('0'),
                unit_price=_estimate_line_base_unit_price(line),
                rate=line.rate or Decimal('0'),
                line_net=line.total or Decimal('0'),
                vat_amount=line.vat_amount or Decimal('0'),
                source_estimate=estimate,
            )
        )
        sort_order += 1
    if bulk:
        ProjectItemLine.objects.bulk_create(bulk)
    return len(bulk)


@transaction.atomic
def create_project_from_estimate(*, estimate, include_items: bool, submitted_by=None):
    """
    Create a new Project, link estimate.project, optionally snapshot estimate lines as
    ProjectItemLine rows (shown under “Items” on the project — not as tasks).
    `estimate` must be quotation-won and not already linked to a project.

    Project fields: ``contract_value`` = estimate selling total (incl. profit + VAT);
    ``budget`` = sum of line base prices (inventory selling price × qty, excl. profit and VAT);
    ``estimated_cost`` is left at zero for manual entry later.
    """
    name = f'{estimate.estimate_number} — {estimate.customer.name}'[:200]
    desc_parts = []
    if estimate.notes:
        desc_parts.append(estimate.notes.strip())
    desc_parts.append(f'Created from estimate {estimate.estimate_number}.')
    description = '\n\n'.join(desc_parts)[:5000]

    from apps.projects.conversion_approval import (
        project_conversion_approval_configured,
        queue_project_conversion_approval,
    )

    needs_conversion_approval = project_conversion_approval_configured()
    initial_status = 'draft' if needs_conversion_approval else 'planning'

    project = Project.objects.create(
        name=name,
        description=description,
        customer=estimate.customer,
        manager=estimate.assigned_to,
        status=initial_status,
        start_date=estimate.date,
        contract_value=estimate.total_amount or Decimal('0.00'),
        budget=estimate.project_budget(),
        estimated_cost=Decimal('0.00'),
    )
    if estimate.assigned_to_id:
        project.members.add(estimate.assigned_to)

    estimate.project = project
    estimate.save(update_fields=['project'])

    if needs_conversion_approval and submitted_by:
        from apps.projects.operation_access import project_skips_approval_gates

        if not project_skips_approval_gates(project):
            queue_project_conversion_approval(submitted_by, project)
        else:
            from apps.projects.conversion_approval import approve_project_conversion

            approve_project_conversion(project)

    if include_items:
        copy_estimate_items_to_project(estimate=estimate, project=project, sort_start=0)

    return project


@transaction.atomic
def link_estimate_to_existing_project(*, estimate, project, include_items: bool, submitted_by=None):
    """
    Link a quotation-won estimate to an existing project and optionally append its lines.

    Does not run conversion approval (that applies only to newly created projects).
    Adds estimate contract total to ``contract_value`` and base-cost total to ``budget``.
    """
    estimate.project = project
    estimate.save(update_fields=['project'])

    project.sync_financials_from_linked_estimates()

    if estimate.assigned_to_id and not project.members.filter(pk=estimate.assigned_to_id).exists():
        project.members.add(estimate.assigned_to)

    if include_items:
        copy_estimate_items_to_project(estimate=estimate, project=project)

    return project
