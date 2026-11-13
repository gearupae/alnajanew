"""Anonymous public form: request inventory items for a project."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.inventory.consumable_project_lines import sync_consumable_request_to_project_item_lines
from apps.inventory.models import ConsumableRequest, ConsumableRequestItem, Item
from apps.inventory.serial_stock import item_available_qty
from apps.projects.item_delivery import project_item_delivered_qty
from apps.projects.models import Project, ProjectItemLine


def get_public_item_request_user():
    User = get_user_model()
    user, _ = User.objects.get_or_create(
        username='public.item.request',
        defaults={
            'first_name': 'Public',
            'last_name': 'Item request',
            'is_active': True,
        },
    )
    return user


def project_allocated_item_ids(project: Project) -> set[int]:
    return set(
        ProjectItemLine.objects.filter(
            project=project,
            inventory_item__isnull=False,
        ).values_list('inventory_item_id', flat=True).distinct()
    )


def build_public_item_catalog(project: Project) -> list[dict]:
    """Products allocated on the project (project item lines) with stock and delivery qty."""
    on_project: dict[int, Decimal] = {}
    for row in (
        ProjectItemLine.objects.filter(project=project, inventory_item__isnull=False)
        .values('inventory_item_id')
        .annotate(t=Sum('quantity'))
    ):
        on_project[row['inventory_item_id']] = row['t'] or Decimal('0')

    allocated_ids = set(on_project.keys())
    if not allocated_ids:
        return []

    catalog = []
    for item in (
        Item.usable()
        .filter(item_type='product', pk__in=allocated_ids)
        .order_by('item_code', 'name')
    ):
        catalog.append(
            {
                'item': item,
                'stock_qty': item_available_qty(item),
                'project_qty': on_project.get(item.pk),
                'delivered_qty': project_item_delivered_qty(project, item),
            }
        )
    return catalog


def parse_public_item_request_post(post, *, project: Project) -> list[tuple[Item, Decimal]]:
    """Validate POST selected_<id> and qty_<id> fields (disabled qty inputs are not submitted)."""
    selected_ids: list[int] = []
    for key, val in post.items():
        if not key.startswith('selected_') or val != '1':
            continue
        raw = key[len('selected_') :]
        if raw.isdigit():
            selected_ids.append(int(raw))

    if not selected_ids:
        raise ValidationError('Select at least one item and enter a quantity.')

    allocated_ids = project_allocated_item_ids(project)
    if not allocated_ids:
        raise ValidationError('This project has no inventory items allocated to request.')

    items_by_id = {
        i.pk: i for i in Item.usable().filter(item_type='product', pk__in=selected_ids)
    }

    lines: list[tuple[Item, Decimal]] = []
    for item_id in selected_ids:
        if item_id not in allocated_ids:
            raise ValidationError('One or more items are not allocated to this project.')
        item = items_by_id.get(item_id)
        if not item:
            continue
        raw_qty = post.get(f'qty_{item_id}', '')
        if raw_qty in (None, ''):
            raise ValidationError(f'Enter a quantity for {item.name}.')
        try:
            qty = Decimal(str(raw_qty).strip().replace(',', '.'))
        except (InvalidOperation, AttributeError, TypeError):
            raise ValidationError(f'Enter a valid quantity for {item.name}.')
        if qty <= 0:
            raise ValidationError(f'Quantity for {item.name} must be greater than zero.')
        qty = Item.normalize_quantity(item, qty)
        if item.requires_whole_quantity() and qty != qty.to_integral_value():
            raise ValidationError(f'{item.name} must be requested in whole units.')
        lines.append((item, qty))

    if not lines:
        raise ValidationError('Select at least one item with quantity greater than zero.')

    return lines


@transaction.atomic
def create_public_project_item_request(
    project: Project,
    lines: list[tuple[Item, Decimal]],
    *,
    requester_name: str = '',
    note: str = '',
) -> ConsumableRequest:
    user = get_public_item_request_user()
    remark_parts = []
    name = (requester_name or '').strip()
    if name:
        remark_parts.append(f'Requested by: {name}')
    note = (note or '').strip()
    if note:
        remark_parts.append(note)
    remark_parts.append('Submitted via public project item request link.')

    consumable_request = ConsumableRequest.objects.create(
        requested_by=user,
        project=project,
        priority='medium',
        status='approved',
        remarks='\n'.join(remark_parts),
        approved_by=user,
        approved_date=timezone.now(),
    )
    for item, qty in lines:
        ConsumableRequestItem.objects.create(
            consumable_request=consumable_request,
            item=item,
            quantity=qty,
        )
    consumable_request.recalculate_total()
    sync_consumable_request_to_project_item_lines(consumable_request)
    return consumable_request


def mark_consumable_requests_fulfilled_when_delivered(project: Project, user) -> None:
    """Set request status to dispensed when every line qty is delivered to the project."""
    for cr in ConsumableRequest.objects.filter(
        project=project,
        is_active=True,
        status__in=('pending', 'approved'),
    ).prefetch_related('items'):
        complete = True
        for item, qty in cr.get_items_for_dispense():
            if project_item_delivered_qty(project, item) < qty:
                complete = False
                break
        if not complete:
            continue
        cr.status = 'dispensed'
        cr.dispensed_by = user
        cr.dispensed_date = timezone.now()
        cr.save(update_fields=['status', 'dispensed_by', 'dispensed_date'])
