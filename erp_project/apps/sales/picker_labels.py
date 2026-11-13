"""Labels for sales form Select2 / project dropdowns."""


def invoice_project_option_label(project_row) -> str:
    """From a .values() row with customer__company / customer__name."""
    company = (project_row.get('customer__company') or '').strip()
    name = (project_row.get('customer__name') or '').strip()
    customer_label = company or name
    code = project_row.get('project_code') or ''
    if customer_label:
        return f'{code} — {customer_label}'
    return code


def invoice_project_choice_label(project) -> str:
    customer = getattr(project, 'customer', None)
    customer_label = ''
    if customer:
        customer_label = (customer.company or '').strip() or (customer.name or '').strip()
    code = project.project_code or ''
    if customer_label:
        return f'{code} — {customer_label}'
    return code
