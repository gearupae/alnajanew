"""Excel export for customer Statement of Account (SOA)."""
from __future__ import annotations

import io
from datetime import date

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from apps.settings_app.models import CompanySettings


def _fmt_d(d) -> str:
    if not d:
        return ''
    return d.strftime('%d/%m/%Y')


def _dec(val) -> float | str:
    if val is None:
        return ''
    return float(val)


def _sheet_title_styles():
    brand = '1e3a5f'
    thin = Side(style='thin', color='CCCCCC')
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    header_fill = PatternFill('solid', fgColor=brand)
    header_font = Font(color='FFFFFF', bold=True, size=11)
    return border, header_fill, header_font, brand


def _write_table(ws, start_row: int, headers: list[str], rows: list[list], *, widths: list[int] | None = None):
    border, header_fill, header_font, _ = _sheet_title_styles()
    for col_idx, label in enumerate(headers, start=1):
        cell = ws.cell(row=start_row, column=col_idx, value=label)
        cell.fill = header_fill
        cell.font = header_font
        cell.border = border
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    amount_cols = {
        col_idx
        for col_idx, label in enumerate(headers, start=1)
        if '(AED)' in str(label) or label.strip().upper().endswith('(AED)')
    }
    for r_off, row in enumerate(rows, start=1):
        for col_idx, value in enumerate(row, start=1):
            cell = ws.cell(row=start_row + r_off, column=col_idx, value=value)
            cell.border = border
            if isinstance(value, (int, float)) and col_idx in amount_cols:
                cell.alignment = Alignment(horizontal='right', vertical='top')
                cell.number_format = '#,##0.00'
            elif isinstance(value, (int, float)):
                cell.alignment = Alignment(horizontal='right', vertical='top')
            else:
                cell.alignment = Alignment(vertical='top', wrap_text=True)
    last_row = start_row + len(rows)
    col_count = len(headers)
    if widths:
        for col_idx, w in enumerate(widths, start=1):
            ws.column_dimensions[get_column_letter(col_idx)].width = w
    if rows:
        ws.auto_filter.ref = f'A{start_row}:{get_column_letter(col_count)}{last_row}'
    return last_row + 2


def export_customer_soa_xlsx(customer, soa_data: dict, *, generated_by: str) -> bytes:
    company = CompanySettings.get_settings()
    summary = soa_data['soa_summary']
    open_invoices = soa_data['soa_open_invoices']
    project_rows = soa_data['soa_projects']
    estimates = soa_data['soa_estimates']

    wb = Workbook()
    ws = wb.active
    ws.title = 'Summary'
    brand = '1e3a5f'

    ws.merge_cells('A1:B1')
    ws['A1'] = company.company_name or 'Company'
    ws['A1'].font = Font(size=14, bold=True, color=brand)
    ws.merge_cells('A2:B2')
    ws['A2'] = 'Statement of account'
    ws['A2'].font = Font(size=12, bold=True)
    ws['A3'] = 'Customer'
    ws['B3'] = (customer.company or customer.name or '').strip()
    ws['A4'] = 'Customer #'
    ws['B4'] = customer.customer_number or ''
    ws['A5'] = 'TRN'
    ws['B5'] = customer.trn or ''
    ws['A6'] = 'Generated'
    ws['B6'] = f'{date.today():%d/%m/%Y} by {generated_by}'

    ws['A8'] = 'Metric'
    ws['B8'] = 'Value'
    ws['A8'].font = ws['B8'].font = Font(bold=True)
    metrics = [
        ('Outstanding balance (AED)', _dec(summary['outstanding'])),
        ('Open invoices (count)', summary['open_invoice_count']),
        ('Open invoices total (AED)', _dec(summary['invoiced_open'])),
        ('Open invoices paid (AED)', _dec(summary['paid_open'])),
        ('Projects (count)', summary['project_count']),
        ('Estimates (count)', summary['estimate_count']),
        ('Estimates combined (AED)', _dec(summary['estimate_total'])),
    ]
    for i, (label, val) in enumerate(metrics, start=9):
        ws.cell(row=i, column=1, value=label)
        ws.cell(row=i, column=2, value=val)
    ws.column_dimensions['A'].width = 36
    ws.column_dimensions['B'].width = 22

    # Open invoices
    ws_inv = wb.create_sheet('Open invoices')
    inv_headers = [
        'Invoice #', 'Date', 'Due', 'Status', 'Project', 'Estimate',
        'Total (AED)', 'Paid (AED)', 'Balance (AED)',
    ]
    inv_rows = []
    for inv in open_invoices:
        project = ''
        if inv.estimate and inv.estimate.project:
            project = inv.estimate.project.project_code
        est = inv.estimate.display_estimate_number if inv.estimate else ''
        inv_rows.append([
            inv.invoice_number,
            _fmt_d(inv.invoice_date),
            _fmt_d(inv.due_date),
            inv.get_status_display(),
            project,
            est,
            _dec(inv.total_amount),
            _dec(inv.paid_amount),
            _dec(inv.balance),
        ])
    if inv_rows:
        inv_rows.append([
            'TOTAL', '', '', '', '', '',
            _dec(summary['invoiced_open']),
            _dec(summary['paid_open']),
            _dec(summary['outstanding']),
        ])
    _write_table(
        ws_inv, 1, inv_headers, inv_rows,
        widths=[16, 12, 12, 14, 14, 16, 14, 14, 14],
    )

    # Projects
    ws_proj = wb.create_sheet('Projects')
    proj_headers = [
        'Code', 'Name', 'Status', 'Contract (AED)', 'Invoiced (AED)',
        'Received (AED)', 'Balance (AED)',
    ]
    proj_rows = []
    for row in project_rows:
        p = row['project']
        proj_rows.append([
            p.project_code,
            p.name,
            p.get_status_display(),
            _dec(row['contract_value']) if row['contract_value'] else '',
            _dec(row['invoiced_amount']),
            _dec(row['received_amount']),
            _dec(row['balance_amount']),
        ])
    _write_table(ws_proj, 1, proj_headers, proj_rows, widths=[14, 28, 14, 16, 16, 16, 16])

    # Estimates
    ws_est = wb.create_sheet('Estimates')
    est_headers = ['Estimate #', 'Date', 'Status', 'Project', 'Total (AED)']
    est_rows = []
    for estimate in estimates:
        proj = estimate.project.project_code if estimate.project else ''
        est_rows.append([
            estimate.display_estimate_number,
            _fmt_d(estimate.date),
            estimate.get_status_display(),
            proj,
            _dec(estimate.total_amount),
        ])
    if est_rows:
        est_rows.append(['TOTAL', '', '', '', _dec(summary['estimate_total'])])
    _write_table(ws_est, 1, est_headers, est_rows, widths=[18, 12, 14, 14, 14])

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
