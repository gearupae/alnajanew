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


def build_public_item_catalog(project: Project) -> list[dict]:
    """Active products with stock on hand and optional qty already on the project."""
    on_project: dict[int, Decimal] = {}
    for row in (
        ProjectItemLine.objects.filter(project=project, inventory_item__isnull=False)
        .values('inventory_item_id')
        .annotate(t=Sum('quantity'))
    ):
        on_project[row['inventory_item_id']] = row['t'] or Decimal('0')

    catalog = []
    for item in Item.usable().filter(item_type='product').order_by('item_code', 'name'):
        catalog.append(
            {
                'item': item,
                'stock_qty': item_available_qty(item),
                'project_qty': on_project.get(item.pk),
                'delivered_qty': project_item_delivered_qty(project, item)
                if item.pk in on_project
                else None,
            }
        )
    return catalog


def parse_public_item_request_post(post) -> list[tuple[Item, Decimal]]:
    """Validate POST item_id[] / qty[] pairs; return (item, qty) lines."""
    item_ids = post.getlist('item_id')
    quantities = post.getlist('quantity')
    selected_flags = post.getlist('selected')

    if not item_ids:
        raise ValidationError('Select at least one item and enter a quantity.')

    lines: list[tuple[Item, Decimal]] = []
    id_set = {int(x) for x in item_ids if str(x).isdigit()}
    items_by_id = {i.pk: i for i in Item.usable().filter(item_type='product', pk__in=id_set)}

    for i, raw_id in enumerate(item_ids):
        if i < len(selected_flags) and selected_flags[i] != '1':
            continue
        if not str(raw_id).isdigit():
            continue
        item = items_by_id.get(int(raw_id))
        if not item:
            continue
        raw_qty = quantities[i] if i < len(quantities) else ''
        try:
            qty = Decimal(str(raw_qty).strip().replace(',', '.'))
        except (InvalidOperation, AttributeError):
            raise ValidationError(f'Invalid quantity for {item.name}.')
        if qty <= 0:
            continue
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
