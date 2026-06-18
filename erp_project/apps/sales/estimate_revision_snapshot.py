"""Store estimate data snapshot before each revision bump."""
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)
from django.db.models import Prefetch

from .models import Estimate, EstimateItem, EstimateRevisionSnapshot


def status_requires_revision_resubmit(status: str) -> bool:
    """Snapshot only when an explicit Revise quotation was requested."""
    return False


def _revision_label_for_count(revision_count: int) -> str:
    if revision_count and revision_count > 0:
        return f'R{revision_count}'
    return ''


def _serialize_estimate_snapshot(estimate: Estimate) -> dict:
    items = []
    for it in estimate.items.all().order_by('sort_order', 'id'):
        items.append({
            'group_name': it.group_name,
            'group_qty_multiplier': str(it.group_qty_multiplier),
            'description': it.description,
            'quantity': str(it.quantity),
            'unit_price': str(it.unit_price),
            'profit_type': it.profit_type,
            'profit_value': str(it.profit_value),
            'rate': str(it.rate),
            'inventory_item_id': it.inventory_item_id,
            'inventory_item_code': it.inventory_item.item_code if it.inventory_item_id else '',
            'tax_code_id': it.tax_code_id,
            'total': str(it.total),
            'vat_amount': str(it.vat_amount),
        })
    rev = estimate.revision_count or 0
    return {
        'estimate_number': estimate.estimate_number,
        'revision_count': rev,
        'display_estimate_number': estimate.display_estimate_number,
        'status': estimate.status,
        'customer_id': estimate.customer_id,
        'customer_name': estimate.customer.name if estimate.customer_id else '',
        'date': estimate.date.isoformat() if estimate.date else '',
        'valid_until': estimate.valid_until.isoformat() if estimate.valid_until else '',
        'subtotal': str(estimate.subtotal),
        'discount_applied': str(estimate.discount_applied),
        'vat_amount': str(estimate.vat_amount),
        'total_amount': str(estimate.total_amount),
        'scope_of_work': estimate.scope_of_work,
        'type_of_work': estimate.type_of_work,
        'type_of_occupancy': estimate.type_of_occupancy,
        'client_note': estimate.client_note,
        'terms_and_conditions': estimate.terms_and_conditions,
        'items': items,
    }


def snapshot_estimate_before_revision(request, estimate: Estimate) -> EstimateRevisionSnapshot | None:
    """
    Capture the current estimate (before save/revision bump) as JSON snapshot.
    PDF is generated lazily on first open (see ensure_revision_snapshot_pdf).
    """
    items_qs = EstimateItem.objects.select_related('inventory_item', 'tax_code').order_by('sort_order', 'id')
    est = (
        Estimate.objects.filter(pk=estimate.pk)
        .select_related('customer')
        .prefetch_related(Prefetch('items', queryset=items_qs))
        .first()
    )
    if not est:
        return None

    rev = est.revision_count or 0
    label = _revision_label_for_count(rev)
    snapshot_data = _serialize_estimate_snapshot(est)

    snap = EstimateRevisionSnapshot(
        estimate=est,
        revision_number=rev,
        revision_label=label,
        status_at_snapshot=est.status,
        total_amount=est.total_amount or Decimal('0.00'),
        snapshot_data=snapshot_data,
        created_by=request.user if getattr(request, 'user', None) and request.user.is_authenticated else None,
    )
    snap.save()
    return snap


def maybe_snapshot_before_revision(
    request,
    estimate: Estimate,
    *,
    pre_status: str,
    has_changes: bool,
    pre_awaiting_resubmit_revision: bool = False,
):
    if not has_changes:
        return None
    needs_snapshot = pre_awaiting_resubmit_revision
    if not needs_snapshot:
        return None
    return snapshot_estimate_before_revision(request, estimate)
