"""Inventory approval routing from Settings → Approval Configuration."""
from __future__ import annotations

from apps.settings_app.models import ApprovalConfiguration


def _get_config(module):
    return ApprovalConfiguration.objects.filter(module=module, is_active=True).first()


def _approver_for_amount(config, amount):
    if not config:
        return None
    if config.approval_type == 'single':
        return config.default_approver
    level = (
        config.levels.filter(is_active=True)
        .order_by('amount_threshold')
        .filter(amount_threshold__gte=amount)
        .first()
    )
    if not level:
        level = config.levels.filter(is_active=True).order_by('-amount_threshold').first()
    return (level.approver if level else None) or config.default_approver


def item_creation_approval_enabled() -> bool:
    return _get_config('inventory_item') is not None


def adjustment_approval_enabled() -> bool:
    return _get_config('inventory_adjustment') is not None


def get_configured_item_approver(item):
    config = _get_config('inventory_item')
    if not config:
        return None
    amount = item.selling_price or item.purchase_price or 0
    return _approver_for_amount(config, amount)


def get_configured_adjustment_approver(movement):
    config = _get_config('inventory_adjustment')
    if not config:
        return None
    return _approver_for_amount(config, movement.total_cost or 0)


def user_can_act_on_item(user, item) -> bool:
    if not user or not user.is_authenticated:
        return False
    if item.status != 'pending_approval':
        return False
    approver = get_configured_item_approver(item)
    if approver is not None:
        return approver.pk == user.pk
    return user.is_superuser


def user_can_act_on_adjustment(user, movement) -> bool:
    if not user or not user.is_authenticated:
        return False
    if movement.approval_status != 'pending':
        return False
    approver = get_configured_adjustment_approver(movement)
    if approver is not None:
        return approver.pk == user.pk
    return user.is_superuser


def user_is_item_approver(user) -> bool:
    config = _get_config('inventory_item')
    if not config:
        return bool(user and user.is_authenticated and user.is_superuser)
    if not user or not user.is_authenticated:
        return False
    if config.default_approver_id == user.pk:
        return True
    if config.approval_type == 'single':
        return False
    return config.levels.filter(is_active=True, approver_id=user.pk).exists()


def user_is_adjustment_approver(user) -> bool:
    config = _get_config('inventory_adjustment')
    if not config:
        return bool(user and user.is_authenticated and user.is_superuser)
    if not user or not user.is_authenticated:
        return False
    if config.default_approver_id == user.pk:
        return True
    if config.approval_type == 'single':
        return False
    return config.levels.filter(is_active=True, approver_id=user.pk).exists()


def pending_items_for_user(user):
    from apps.inventory.models import Item

    if not user or not user.is_authenticated:
        return []
    qs = (
        Item.objects.filter(is_active=True, status='pending_approval')
        .select_related('category', 'submitted_by')
        .order_by('-submitted_at', '-pk')
    )
    return [item for item in qs if user_can_act_on_item(user, item)]


def pending_adjustments_for_user(user):
    from apps.inventory.models import StockMovement

    if not user or not user.is_authenticated:
        return []
    qs = (
        StockMovement.objects.filter(
            is_active=True,
            approval_status='pending',
            movement_type__in=('adjustment_plus', 'adjustment_minus'),
        )
        .select_related('item', 'warehouse', 'submitted_by')
        .order_by('-created_at')
    )
    return [mv for mv in qs if user_can_act_on_adjustment(user, mv)]
