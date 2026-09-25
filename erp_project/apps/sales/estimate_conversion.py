"""Estimate → project / invoice conversion helpers."""
from __future__ import annotations

from decimal import Decimal

from apps.crm.customer_compliance import (
    b2b_compliance_warning_message,
    b2b_has_compliance_for_project_conversion,
    customer_is_b2b,
    project_conversion_compliance_missing_labels,
)


def estimate_customer_b2b_compliance_ok(estimate) -> bool:
    customer = getattr(estimate, 'customer', None)
    return b2b_has_compliance_for_project_conversion(customer)


def estimate_convert_to_project_block_reason(estimate) -> str:
    """
    Empty string if conversion is allowed (status/permissions checked elsewhere).
    """
    if not estimate.allows_follow_on_conversion:
        return 'Only quotation-won estimates can be converted to a project.'
    if estimate.project_id:
        project = estimate.project
        if project and getattr(project, 'status', None) == 'draft':
            if getattr(project, 'conversion_approval_status', 'none') == 'pending':
                return (
                    f'A project ({project.project_code}) is already awaiting conversion approval. '
                    'Open the project to approve or reject it.'
                )
        return 'This estimate is already linked to a project.'
    if not estimate_customer_b2b_compliance_ok(estimate):
        missing = project_conversion_compliance_missing_labels(estimate.customer)
        if missing:
            extra = (
                ' B2B customers also need trade license number and document.'
                if customer_is_b2b(estimate.customer)
                else ''
            )
            return (
                'Customer must have VAT (TRN) and TRN document on file before converting to a project.'
                f'{extra} '
                f'Missing: {", ".join(missing)}. '
                'Update the customer record in CRM, then convert to project.'
            )
    return ''


def warn_on_quotation_won_if_b2b_incomplete(estimate) -> str:
    """Warning message after marking won (B2B only); empty if nothing to warn."""
    return b2b_compliance_warning_message(estimate.customer)


def estimate_show_b2b_compliance_banner(estimate) -> bool:
    return (
        estimate.status == 'quotation_won'
        and not estimate_customer_b2b_compliance_ok(estimate)
        and not estimate.project_id
    )


def eligible_existing_projects_for_estimate(estimate, user):
    """Active ongoing projects for the same customer that can receive another quotation."""
    from apps.core.visibility import filter_projects_for_user
    from apps.projects.models import Project

    if not estimate.customer_id:
        return Project.objects.none()

    qs = Project.objects.filter(
        is_active=True,
        customer_id=estimate.customer_id,
        status__in=['planning', 'in_progress', 'on_hold', 'completed'],
    ).exclude(
        conversion_approval_status='pending',
    ).order_by('-start_date', '-pk')
    return filter_projects_for_user(qs, user)


def existing_project_link_block_reason(estimate, project) -> str:
    """Empty if estimate may be linked to this project."""
    if not project:
        return 'Select a project.'
    if not project.is_active:
        return 'That project is not active.'
    if project.status == 'cancelled':
        return 'Cannot link to a cancelled project.'
    if project.status == 'draft':
        return 'Cannot link to a draft project awaiting setup.'
    if project.conversion_approval_status == 'pending':
        return 'That project is still awaiting conversion approval.'
    if estimate.customer_id and project.customer_id != estimate.customer_id:
        return 'The project must belong to the same customer as this quotation.'
    return ''


def copy_estimate_lines_to_invoice(estimate, invoice):
    """
    Copy estimate lines to an invoice, applying header discount allocations so
    invoice totals match the estimate grand total.
    """
    from .models import InvoiceItem
    from .vat_pricing import line_uses_inclusive_pricing, sync_document_line_vat_flags

    estimate.calculate_totals()
    items = list(estimate.items.order_by('sort_order', 'id'))
    if not items:
        sync_document_line_vat_flags(invoice)
        invoice.calculate_totals()
        return invoice

    line_amounts, _, _discount_amt = estimate.discounted_line_amounts(items)
    for item, (line_net, line_vat) in zip(items, line_amounts):
        qty = item.quantity or Decimal('1')
        if qty <= 0:
            qty = Decimal('1')
        inclusive = line_uses_inclusive_pricing(item)
        if inclusive:
            line_gross = (line_net + line_vat).quantize(Decimal('0.01'))
            unit_price = (line_gross / qty).quantize(Decimal('0.01'))
        else:
            unit_price = (line_net / qty).quantize(Decimal('0.01'))
        InvoiceItem.objects.create(
            invoice=invoice,
            description=item.description,
            quantity=qty,
            unit_price=unit_price,
            tax_code=item.tax_code,
            vat_rate=item.vat_rate,
            is_vat_inclusive=inclusive,
        )

    sync_document_line_vat_flags(invoice)
    invoice.calculate_totals()
    apply_estimate_totals_to_invoice(estimate, invoice)
    return invoice


def apply_estimate_totals_to_invoice(estimate, invoice):
    """Ensure invoice header totals match the source quotation after conversion."""
    estimate.calculate_totals()
    net_subtotal = (estimate.subtotal or Decimal('0')) - (estimate.discount_applied or Decimal('0'))
    invoice.subtotal = net_subtotal.quantize(Decimal('0.01'))
    invoice.vat_amount = (estimate.vat_amount or Decimal('0')).quantize(Decimal('0.01'))
    invoice.round_off = estimate.round_off if estimate.round_off is not None else Decimal('0.00')
    invoice.total_amount = (estimate.total_amount or Decimal('0')).quantize(Decimal('0.01'))
    invoice.save(update_fields=['subtotal', 'vat_amount', 'total_amount', 'round_off'])
    return invoice

