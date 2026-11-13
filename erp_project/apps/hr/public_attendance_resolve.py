"""Resolve employee on the public attendance punch page (code or name)."""

from __future__ import annotations

from django.db.models import Q, Value
from django.db.models.functions import Concat

from apps.hr.models import Employee


def resolve_employee_for_public_attendance(raw: str) -> tuple[Employee | None, str | None]:
    """
    Match active employee by employee code or name.
    Returns (employee, error_message).
    """
    q = (raw or '').strip()
    if not q:
        return None, 'Employee code or name is required.'

    emp = Employee.objects.filter(is_active=True, employee_code__iexact=q).first()
    if emp:
        return emp, None

    if ' ' in q:
        first, last = q.split(None, 1)
        emp = Employee.objects.filter(
            is_active=True,
            first_name__iexact=first,
            last_name__iexact=last,
        ).first()
        if emp:
            return emp, None

    qs = (
        Employee.objects.filter(is_active=True)
        .annotate(_full=Concat('first_name', Value(' '), 'last_name'))
        .filter(
            Q(employee_code__icontains=q)
            | Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(_full__icontains=q)
        )
        .order_by('first_name', 'last_name', 'employee_code')
    )
    matches = list(qs[:12])
    if len(matches) == 1:
        return matches[0], None
    if not matches:
        return None, 'Employee not found.'
    return None, 'Several employees match — enter your full employee code (e.g. EMP-2026-0002).'


def public_employee_search_rows(query: str, *, limit: int = 20) -> list[dict]:
    q = (query or '').strip()
    if len(q) < 2:
        return []
    rows = (
        Employee.objects.filter(is_active=True)
        .annotate(_full=Concat('first_name', Value(' '), 'last_name'))
        .filter(
            Q(employee_code__icontains=q)
            | Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(_full__icontains=q)
        )
        .order_by('first_name', 'last_name', 'employee_code')[:limit]
    )
    return [
        {
            'id': emp.pk,
            'code': emp.employee_code,
            'text': f'{emp.employee_code} — {emp.full_name}',
        }
        for emp in rows
    ]
