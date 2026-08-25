"""Lead report aggregations (period-wise)."""
from __future__ import annotations

from decimal import Decimal

from django.db.models import Count, OuterRef, Q, Subquery, Sum
from django.db.models.functions import Coalesce

from apps.crm.models import CrmLeadKanbanStage, Customer
from apps.crm.utils import (
    filter_customers_for_user,
    get_sales_employee_queryset,
    salesperson_display_name,
)
from apps.sales.models import Estimate
from apps.settings_app.models import AuditLog


def _build_lead_salesperson_performance(
    active_leads,
    leads_with_value,
    period_lead_ids,
    start_date,
    end_date,
):
    """Per-salesperson lead counts, pipeline value, and conversions."""
    rows = []
    entries = [
        {'id': emp.pk, 'label': salesperson_display_name(emp)}
        for emp in get_sales_employee_queryset()
    ]
    entries.append({'id': None, 'label': 'Unassigned'})

    conversion_filter = (
        Q(changes__action='converted_to_customer')
        | Q(changes__converted_to_customer=True)
        | Q(changes__action='kanban_won')
    )
    period_leads = Customer.objects.filter(pk__in=period_lead_ids, customer_type='lead')

    for entry in entries:
        if entry['id'] is None:
            sp_leads = active_leads.filter(assigned_salesperson__isnull=True)
            sp_value_qs = leads_with_value.filter(assigned_salesperson__isnull=True)
            sp_period_ids = list(
                period_leads.filter(assigned_salesperson__isnull=True).values_list('pk', flat=True)
            )
        else:
            sp_leads = active_leads.filter(assigned_salesperson_id=entry['id'])
            sp_value_qs = leads_with_value.filter(assigned_salesperson_id=entry['id'])
            sp_period_ids = list(
                period_leads.filter(assigned_salesperson_id=entry['id']).values_list('pk', flat=True)
            )

        pipeline = (
            sp_value_qs.aggregate(total=Coalesce(Sum('latest_estimate_value'), Decimal('0.00')))['total']
            or Decimal('0.00')
        )
        converted = 0
        if sp_period_ids:
            converted = (
                AuditLog.objects.filter(
                    model='Customer',
                    timestamp__date__gte=start_date,
                    timestamp__date__lte=end_date,
                    record_id__in=[str(pk) for pk in sp_period_ids],
                )
                .filter(conversion_filter)
                .values('record_id')
                .distinct()
                .count()
            )

        lead_count = sp_leads.count()
        rows.append({
            'label': entry['label'],
            'lead_count': lead_count,
            'pipeline_value': pipeline,
            'converted_count': converted,
            'conversion_rate_pct': int((converted / lead_count) * 100) if lead_count else 0,
            'won_count': sp_leads.filter(lead_kanban_stage__converts_to_customer=True).count(),
            'lost_count': sp_leads.filter(lead_kanban_stage__slug='lost').count(),
        })

    rows.sort(key=lambda r: (r['pipeline_value'], r['lead_count']), reverse=True)
    return [row for row in rows if row['lead_count'] or row['converted_count']] or rows[:1]


def _apply_lead_filters(qs, *, stage='', salesperson='', lead_status=''):
    if lead_status:
        qs = qs.filter(status=lead_status)
    if salesperson == 'none':
        qs = qs.filter(assigned_salesperson__isnull=True)
    elif salesperson:
        try:
            qs = qs.filter(assigned_salesperson_id=int(salesperson))
        except (TypeError, ValueError):
            pass
    if stage == 'unassigned':
        qs = qs.filter(lead_kanban_stage__isnull=True)
    elif stage:
        try:
            qs = qs.filter(lead_kanban_stage_id=int(stage))
        except (TypeError, ValueError):
            pass
    return qs


def build_lead_report(
    *,
    start_date,
    end_date,
    stage='',
    salesperson='',
    lead_status='',
    user=None,
):
    """
    Period-wise lead metrics with optional stage / status / salesperson filters.
    """
    leads_created = Customer.objects.filter(
        is_active=True,
        created_at__date__gte=start_date,
        created_at__date__lte=end_date,
    )
    if user:
        leads_created = filter_customers_for_user(leads_created, user)

    active_leads = leads_created.filter(customer_type='lead')
    active_leads = _apply_lead_filters(
        active_leads,
        stage=stage,
        salesperson=salesperson,
        lead_status=lead_status,
    )

    latest_estimate_subq = (
        Estimate.objects.filter(
            customer=OuterRef('pk'),
            is_active=True,
        )
        .order_by('-date', '-id')
        .values('total_amount')[:1]
    )

    leads_with_value = active_leads.annotate(
        latest_estimate_value=Subquery(latest_estimate_subq),
    )
    pipeline_value = (
        leads_with_value.aggregate(
            total=Coalesce(Sum('latest_estimate_value'), Decimal('0.00')),
        )['total']
        or Decimal('0.00')
    )

    estimate_value_in_period = (
        Estimate.objects.filter(
            is_active=True,
            customer__in=active_leads,
            date__gte=start_date,
            date__lte=end_date,
        ).aggregate(total=Coalesce(Sum('total_amount'), Decimal('0.00')))['total']
        or Decimal('0.00')
    )

    stage_rows = []
    stages = CrmLeadKanbanStage.objects.filter(is_active=True).order_by('sort_order', 'id')
    stage_counts = {
        row['lead_kanban_stage_id']: row['count']
        for row in active_leads.values('lead_kanban_stage_id').annotate(count=Count('id'))
    }
    for st in stages:
        stage_rows.append({
            'id': st.id,
            'name': st.name,
            'slug': st.slug,
            'count': stage_counts.get(st.id, 0),
            'converts_to_customer': st.converts_to_customer,
        })

    unassigned_count = active_leads.filter(lead_kanban_stage__isnull=True).count()

    period_lead_ids = list(leads_created.values_list('pk', flat=True))
    converted_count = (
        AuditLog.objects.filter(
            model='Customer',
            timestamp__date__gte=start_date,
            timestamp__date__lte=end_date,
            record_id__in=[str(pk) for pk in period_lead_ids],
        )
        .filter(
            Q(changes__action='converted_to_customer')
            | Q(changes__converted_to_customer=True)
            | Q(changes__action='kanban_won')
        )
        .values('record_id')
        .distinct()
        .count()
    )

    conversion_rate_pct = 0
    if total_leads := leads_created.filter(customer_type='lead').count():
        conversion_rate_pct = int((converted_count / total_leads) * 100)

    salesperson_performance = _build_lead_salesperson_performance(
        active_leads,
        leads_with_value,
        period_lead_ids,
        start_date,
        end_date,
    )

    lead_details = []
    for lead in (
        leads_with_value.select_related(
            'lead_kanban_stage',
            'assigned_salesperson',
            'assigned_salesperson__designation',
        )
        .order_by('-created_at')[:500]
    ):
        lead_details.append({
            'pk': lead.pk,
            'customer_number': lead.customer_number,
            'name': lead.name,
            'company': lead.company,
            'phone': lead.phone,
            'email': lead.email,
            'city': lead.city,
            'job_type': lead.get_job_type_display() if lead.job_type else '',
            'status': lead.get_status_display(),
            'status_code': lead.status,
            'created_at': lead.created_at,
            'stage_name': lead.lead_kanban_stage.name if lead.lead_kanban_stage_id else 'Unassigned',
            'stage_slug': lead.lead_kanban_stage.slug if lead.lead_kanban_stage_id else 'unassigned',
            'salesperson_name': salesperson_display_name(lead.assigned_salesperson),
            'latest_estimate_value': lead.latest_estimate_value,
        })

    all_stage_counts = [row['count'] for row in stage_rows] + [unassigned_count]
    stage_max_count = max(all_stage_counts) if any(all_stage_counts) else 1

    salespeople = [
        {'id': emp.pk, 'label': salesperson_display_name(emp)}
        for emp in get_sales_employee_queryset()
    ]

    return {
        'start_date': start_date,
        'end_date': end_date,
        'filter_stage': stage,
        'filter_salesperson': salesperson,
        'filter_status': lead_status,
        'filter_stages': stage_rows,
        'filter_salespeople': salespeople,
        'filter_status_choices': Customer.STATUS_CHOICES,
        'total_leads_created': leads_created.filter(customer_type='lead').count(),
        'active_leads_count': active_leads.count(),
        'converted_count': converted_count,
        'conversion_rate_pct': conversion_rate_pct,
        'salesperson_performance': salesperson_performance,
        'pipeline_value': pipeline_value,
        'estimate_value_in_period': estimate_value_in_period,
        'stage_rows': stage_rows,
        'unassigned_count': unassigned_count,
        'lead_details': lead_details,
        'lost_count': next(
            (row['count'] for row in stage_rows if row['slug'] == 'lost'),
            0,
        ),
        'won_stage_count': next(
            (row['count'] for row in stage_rows if row['converts_to_customer']),
            0,
        ),
        'negotiation_count': next(
            (row['count'] for row in stage_rows if 'negotiat' in row['slug'] or 'negotiat' in row['name'].lower()),
            0,
        ),
        'stage_max_count': stage_max_count,
    }
