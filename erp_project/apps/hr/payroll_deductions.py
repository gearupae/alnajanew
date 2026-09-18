"""Payroll manual deduction lines — draft form sync from POST."""
from __future__ import annotations

from decimal import Decimal

from django.db.models import Sum

from apps.hr.models_extended import PayrollDeductionLine

MANUAL_DEDUCTION_CHOICES = [
    (PayrollDeductionLine.CODE_OTHER, 'Other'),
    ('loan', 'Loan repayment'),
    ('penalty', 'Penalty / fine'),
    ('uniform', 'Uniform / equipment'),
    ('insurance', 'Insurance (employee)'),
]

MANUAL_DEDUCTION_CODES = {code for code, _ in MANUAL_DEDUCTION_CHOICES} | {
    PayrollDeductionLine.CODE_MANUAL,
}

MANUAL_DEDUCTION_DEFAULT_LABEL = {
    PayrollDeductionLine.CODE_OTHER: 'Other deduction',
    'loan': 'Loan repayment',
    'penalty': 'Penalty / fine',
    'uniform': 'Uniform / equipment',
    'insurance': 'Insurance (employee)',
}


def manual_deduction_label(code: str) -> str:
    return dict(MANUAL_DEDUCTION_CHOICES).get(code, code.replace('_', ' ').title())


def default_manual_deduction_description(code: str) -> str:
    return MANUAL_DEDUCTION_DEFAULT_LABEL.get(code, manual_deduction_label(code))


def total_manual_deductions_amount(payroll) -> Decimal:
    t = (
        PayrollDeductionLine.objects.filter(payroll=payroll, code__in=MANUAL_DEDUCTION_CODES).aggregate(s=Sum('amount'))[
            's'
        ]
        or Decimal('0')
    )
    return t.quantize(Decimal('0.01'))


def manual_deduction_rows_for_payroll(payroll) -> list[dict]:
    rows = []
    if payroll and payroll.pk:
        for ln in PayrollDeductionLine.objects.filter(payroll=payroll, code__in=MANUAL_DEDUCTION_CODES).order_by('pk'):
            rows.append(
                {
                    'code': ln.code if ln.code in MANUAL_DEDUCTION_CODES else PayrollDeductionLine.CODE_OTHER,
                    'description': ln.label,
                    'amount': str(ln.amount),
                }
            )
    if not rows and payroll and (payroll.deductions or Decimal('0')) > 0:
        rows.append(
            {
                'code': PayrollDeductionLine.CODE_OTHER,
                'description': 'Manual / other deductions',
                'amount': str(payroll.deductions),
            }
        )
    if not rows:
        rows = [{'code': PayrollDeductionLine.CODE_OTHER, 'description': '', 'amount': ''}]
    return rows


def refresh_payroll_manual_deductions_total(payroll, *, save: bool = True) -> Decimal:
    total = total_manual_deductions_amount(payroll)
    payroll.deductions = total
    if save:
        payroll.save(update_fields=['deductions'])
    return total


def get_or_create_draft_payroll(employee, month_first):
    from apps.hr.models import Payroll

    payroll, _created = Payroll.objects.get_or_create(
        employee=employee,
        month=month_first,
        defaults={
            'status': 'draft',
            'basic_salary': employee.basic_salary or Decimal('0'),
            'company_id': employee.company_id,
            'is_active': True,
        },
    )
    return payroll


def add_manual_deduction_line(payroll, code: str, label: str, amount: Decimal):
    if payroll.status != 'draft':
        from django.core.exceptions import ValidationError

        raise ValidationError('Cannot add deductions to a processed or paid payroll.')
    amt = amount.quantize(Decimal('0.01'))
    if amt <= 0:
        from django.core.exceptions import ValidationError

        raise ValidationError('Deduction amount must be greater than zero.')
    code = (code or PayrollDeductionLine.CODE_OTHER).strip()[:40]
    label = (label or default_manual_deduction_description(code)).strip()[:200]
    PayrollDeductionLine.objects.create(
        payroll=payroll,
        code=code,
        label=label,
        amount=amt,
    )
    return refresh_payroll_manual_deductions_total(payroll)


def add_manual_deduction_for_employee_month(*, employee, month_first, code: str, label: str, amount: Decimal):
    from apps.hr.salary_payroll_utils import ensure_payroll_allowances_from_employee_template

    payroll = get_or_create_draft_payroll(employee, month_first)
    if payroll.status != 'draft':
        from django.core.exceptions import ValidationError

        raise ValidationError(
            f'Payroll for {employee.full_name} ({month_first.strftime("%B %Y")}) is already {payroll.status}.'
        )
    ensure_payroll_allowances_from_employee_template(payroll, employee)
    add_manual_deduction_line(payroll, code, label, amount)
    return payroll


def replace_manual_deduction_lines_from_post(payroll, post_data) -> Decimal:
    """
    Replace manual deduction lines for a draft payroll from form POST.
    Updates payroll.deductions to the sum of manual rows.
    """
    if payroll.status != 'draft':
        return payroll.deductions or Decimal('0')

    PayrollDeductionLine.objects.filter(payroll=payroll, code__in=MANUAL_DEDUCTION_CODES).delete()

    codes = post_data.getlist('deduction_code[]')
    descriptions = post_data.getlist('deduction_description[]')
    amounts = post_data.getlist('deduction_amount[]')
    total = Decimal('0')

    for i, code in enumerate(codes):
        code = (code or '').strip()
        if not code:
            continue
        desc = (descriptions[i] if i < len(descriptions) else '').strip() or default_manual_deduction_description(code)
        raw_amt = (amounts[i] if i < len(amounts) else '') or '0'
        try:
            amt = Decimal(str(raw_amt).replace(',', '').strip())
        except Exception:
            amt = Decimal('0')
        if amt <= 0:
            continue
        amt = amt.quantize(Decimal('0.01'))
        total += amt
        PayrollDeductionLine.objects.create(
            payroll=payroll,
            code=code[:40],
            label=desc[:200],
            amount=amt,
        )

    total = total.quantize(Decimal('0.01'))
    payroll.deductions = total
    payroll.save(update_fields=['deductions'])
    return total
