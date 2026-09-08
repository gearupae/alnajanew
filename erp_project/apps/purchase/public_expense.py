"""Public employee expense bill submission (no login)."""
from __future__ import annotations

import os
import re
from datetime import date
from decimal import Decimal, InvalidOperation

from django.db.models import Q
from django.utils.text import get_valid_filename

from apps.hr.models import Employee


def resolve_employee_for_public_expense(code: str):
    """Return (employee, error_message)."""
    code = (code or '').strip()
    if not code:
        return None, 'Employee code is required.'
    emp = (
        Employee.objects.filter(employee_code__iexact=code, is_active=True)
        .select_related('user')
        .first()
    )
    if not emp:
        return None, 'Employee not found for this code.'
    if not emp.user_id:
        return (
            None,
            'Your employee profile is not linked to a user account. Contact HR or finance.',
        )
    return emp, ''


def projects_for_public_expense(employee):
    """Active projects the employee is assigned to (member, technician, or manager)."""
    from apps.projects.models import Project

    user = employee.user
    if not user:
        return Project.objects.none()
    return (
        Project.objects.filter(is_active=True)
        .exclude(status__in=['draft', 'cancelled'])
        .filter(Q(members=user) | Q(technicians=user) | Q(manager=user))
        .distinct()
        .order_by('-start_date', '-pk')
    )


def guess_bill_line_from_filename(filename: str) -> dict:
    """Best-effort metadata from the uploaded filename."""
    base = os.path.splitext(get_valid_filename(filename or 'Bill'))[0]
    description = base.replace('_', ' ').replace('-', ' ').strip() or 'Expense bill'
    amount = Decimal('0.00')
    for pattern in (r'(\d+[.,]\d{2})', r'(\d+)'):
        match = re.search(pattern, base.replace(',', ''))
        if not match:
            continue
        try:
            parsed = Decimal(match.group(1).replace(',', '.')).quantize(Decimal('0.01'))
            if parsed > 0:
                amount = parsed
                break
        except (InvalidOperation, ValueError):
            continue
    return {
        'description': description[:500],
        'amount': amount,
        'date': date.today(),
    }


def create_public_expense_claim(*, employee, project, files, description=''):
    """Create a submitted expense claim with one line per uploaded bill."""
    from apps.finance.models import TaxCode

    from .models import ExpenseClaim, ExpenseClaimItem

    claim = ExpenseClaim.objects.create(
        employee=employee.user,
        project=project,
        claim_date=date.today(),
        description=(description or '').strip()[:5000],
        status='submitted',
    )
    default_tax = TaxCode.objects.filter(is_active=True, rate=5).first()
    created = 0
    for uploaded in files:
        meta = guess_bill_line_from_filename(uploaded.name)
        ExpenseClaimItem.objects.create(
            expense_claim=claim,
            date=meta['date'],
            category='other',
            description=meta['description'],
            amount=meta['amount'],
            tax_code=default_tax if meta['amount'] > 0 else None,
            has_receipt=True,
            receipt=uploaded,
        )
        created += 1
    claim.calculate_totals()
    return claim, created
