"""Document expiry classification, entity linking, and lookup helpers."""
from __future__ import annotations

from datetime import date
from urllib.parse import quote

from django.urls import reverse


def document_status(doc, today: date | None = None) -> str:
    """Return expired | expiring | active using the document type's alert threshold."""
    today = today or date.today()
    if not doc.expiry_date:
        return 'active'
    days = (doc.expiry_date - today).days
    if days < 0:
        return 'expired'
    alert_days = getattr(doc.document_type, 'alert_days_before', None)
    if alert_days is not None and days <= alert_days:
        return 'expiring'
    return 'active'


def filter_documents_by_status(queryset, status: str, today: date | None = None):
    if not status:
        return queryset
    today = today or date.today()
    pks = [
        doc.pk
        for doc in queryset.select_related('document_type')
        if document_status(doc, today) == status
    ]
    if not pks:
        return queryset.none()
    return (
        queryset.model.objects.filter(pk__in=pks)
        .select_related('document_type')
        .order_by('-created_at', '-pk')
    )


def document_status_counts(queryset, today: date | None = None) -> dict[str, int]:
    today = today or date.today()
    counts = {'expired': 0, 'expiring': 0, 'active': 0}
    for doc in queryset.select_related('document_type'):
        counts[document_status(doc, today)] += 1
    return counts


def _employee_label(emp) -> str:
    return (emp.full_name or emp.employee_code or str(emp)).strip()


def _customer_label(cust) -> str:
    return (cust.company or cust.name or str(cust)).strip()


def resolve_entity(entity_type: str, entity_id: int | None) -> tuple[bool, str]:
    """Validate entity_id exists for entity_type; return (ok, display_name)."""
    if not entity_id:
        return True, ''
    try:
        entity_id = int(entity_id)
    except (TypeError, ValueError):
        return False, ''

    if entity_type == 'employee':
        from apps.hr.models import Employee

        obj = Employee.objects.filter(pk=entity_id, is_active=True).first()
        return (bool(obj), _employee_label(obj) if obj else '')
    if entity_type == 'customer':
        from apps.crm.models import Customer

        obj = Customer.objects.filter(pk=entity_id, is_active=True).first()
        return (bool(obj), _customer_label(obj) if obj else '')
    if entity_type == 'vendor':
        from apps.purchase.models import Vendor

        obj = Vendor.objects.filter(pk=entity_id, is_active=True).first()
        return (bool(obj), (obj.name if obj else ''))
    if entity_type == 'vehicle':
        from apps.fleet.models import Vehicle

        obj = Vehicle.objects.filter(pk=entity_id, is_active=True).first()
        return (bool(obj), str(obj) if obj else '')
    if entity_type == 'company':
        from apps.settings_app.models import Company

        obj = Company.objects.filter(pk=entity_id, is_active=True).first()
        return (bool(obj), (obj.name if obj else ''))
    return True, ''


def entity_detail_url(entity_type: str, entity_id: int | None):
    if not entity_id:
        return None
    try:
        pk = int(entity_id)
    except (TypeError, ValueError):
        return None
    if entity_type == 'employee':
        return reverse('hr:employee_detail', kwargs={'pk': pk})
    if entity_type == 'customer':
        return reverse('crm:customer_detail', kwargs={'pk': pk})
    if entity_type == 'vendor':
        return reverse('purchase:vendor_edit', kwargs={'pk': pk})
    if entity_type == 'vehicle':
        return reverse('fleet:vehicle_edit', kwargs={'pk': pk})
    return None


def lookup_entities(entity_type: str, query: str = '', limit: int = 25) -> list[dict]:
    from django.db.models import Q

    query = (query or '').strip()
    limit = max(1, min(limit, 50))
    rows: list[dict] = []

    if entity_type == 'employee':
        from apps.hr.models import Employee

        qs = Employee.objects.filter(is_active=True).order_by('first_name', 'last_name')
        if query:
            qs = qs.filter(
                Q(first_name__icontains=query)
                | Q(last_name__icontains=query)
                | Q(employee_code__icontains=query)
            )
        for emp in qs[:limit]:
            rows.append({'id': emp.pk, 'text': _employee_label(emp)})
    elif entity_type == 'customer':
        from apps.crm.models import Customer

        qs = Customer.objects.filter(is_active=True).order_by('company', 'name')
        if query:
            qs = qs.filter(Q(company__icontains=query) | Q(name__icontains=query))
        for cust in qs[:limit]:
            rows.append({'id': cust.pk, 'text': _customer_label(cust)})
    elif entity_type == 'vendor':
        from apps.purchase.models import Vendor

        qs = Vendor.objects.filter(is_active=True).order_by('name')
        if query:
            qs = qs.filter(name__icontains=query)
        for ven in qs[:limit]:
            rows.append({'id': ven.pk, 'text': ven.name})
    elif entity_type == 'vehicle':
        from apps.fleet.models import Vehicle

        qs = Vehicle.objects.filter(is_active=True).order_by('plate_number', 'make')
        if query:
            qs = qs.filter(
                Q(plate_number__icontains=query)
                | Q(make__icontains=query)
                | Q(model__icontains=query)
            )
        for veh in qs[:limit]:
            rows.append({'id': veh.pk, 'text': str(veh)})
    elif entity_type == 'company':
        from apps.settings_app.models import Company

        qs = Company.objects.filter(is_active=True).order_by('name')
        if query:
            qs = qs.filter(name__icontains=query)
        for co in qs[:limit]:
            rows.append({'id': co.pk, 'text': co.name})
    return rows


def entity_document_create_url(entity_type: str, entity_id: int, entity_name: str) -> str:
    base = reverse('documents:document_create')
    return (
        f'{base}?entity_type={quote(entity_type)}'
        f'&entity_id={entity_id}'
        f'&entity_name={quote(entity_name or "")}'
    )


def entity_documents_context(user, *, entity_type: str, entity_id: int, entity_name: str) -> dict:
    from apps.core.utils import PermissionChecker
    from apps.documents.models import Document

    docs = (
        Document.objects.filter(
            is_active=True,
            entity_type=entity_type,
            entity_id=entity_id,
        )
        .select_related('document_type')
        .order_by('expiry_date', '-created_at')
    )
    return {
        'entity_documents': docs,
        'entity_documents_expired': sum(1 for d in docs if d.is_expired),
        'entity_documents_expiring': sum(1 for d in docs if d.is_expiring_soon),
        'can_create_document': user.is_superuser
        or PermissionChecker.has_permission(user, 'documents', 'create'),
        'entity_document_create_url': entity_document_create_url(
            entity_type, entity_id, entity_name
        ),
        'can_view_documents': user.is_superuser
        or PermissionChecker.has_permission(user, 'documents', 'view'),
    }
