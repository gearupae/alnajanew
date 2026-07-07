"""Sales Tax Credit Note views."""
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.core.mixins import CreatePermissionMixin, PermissionRequiredMixin, UpdatePermissionMixin
from apps.core.utils import PermissionChecker
from apps.settings_app.models import CompanySettings

from .forms import CreditNoteForm
from .models import CreditNote, CreditNoteLine, Invoice, InvoiceItem

FTA_LATE_WARNING = (
    'FTA requires Tax Credit Notes within 14 days of the event (Art. 62(2)). '
    'Late issuance may attract penalties. Issuance remains mandatory — you can proceed.'
)


class CreditNoteListView(PermissionRequiredMixin, ListView):
    model = CreditNote
    template_name = 'sales/credit_note_list.html'
    context_object_name = 'credit_notes'
    module_name = 'sales'
    permission_type = 'view'
    paginate_by = 25

    def get_queryset(self):
        qs = CreditNote.objects.filter(is_active=True).select_related(
            'customer', 'original_invoice', 'journal_entry'
        )
        search = self.request.GET.get('search')
        if search:
            qs = qs.filter(
                Q(number__icontains=search)
                | Q(customer__name__icontains=search)
                | Q(original_invoice__invoice_number__icontains=search)
            )
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Credit Notes'
        context['status_choices'] = CreditNote.STATUS_CHOICES
        context['can_create'] = (
            self.request.user.is_superuser
            or PermissionChecker.has_permission(self.request.user, 'sales', 'create')
        )
        return context


def _credit_note_invoice_payload(invoice, exclude_credit_note_pk=None):
    """Shared invoice + line data for credit note create (server template and AJAX)."""
    prior = CreditNote.posted_total_for_invoice(
        invoice,
        exclude_pk=exclude_credit_note_pk,
    )
    lines = []
    for row in _invoice_line_rows(invoice, exclude_credit_note_pk):
        lines.append({
            'invoice_line_id': row['invoice_line_id'],
            'description': row['description'],
            'quantity': str(row['quantity']),
            'max_quantity': str(row['max_quantity']),
            'unit_price': str(row['unit_price']),
            'vat_rate': str(row['vat_rate']),
            'is_vat_inclusive': bool(row['is_vat_inclusive']),
            'line_total': str(row['line_total']),
            'line_vat': str(row['line_vat']),
        })
    return {
        'invoice_number': invoice.invoice_number,
        'customer_name': invoice.customer.name,
        'customer_trn': invoice.customer.trn or '',
        'invoice_total': str(invoice.total_amount),
        'prior_credited': str(prior),
        'remaining_invoice_value': str(invoice.total_amount - prior),
        'max_credit': str(invoice.total_amount - prior),
        'lines': lines,
    }


def _credit_note_invoice_context(invoice, exclude_credit_note_pk=None):
    """Template context fragment for a selected invoice."""
    payload = _credit_note_invoice_payload(invoice, exclude_credit_note_pk)
    line_rows = []
    for row in _invoice_line_rows(invoice, exclude_credit_note_pk):
        line_rows.append(row)
    return {
        'selected_invoice': invoice,
        'customer_name': payload['customer_name'],
        'customer_trn': payload['customer_trn'],
        'invoice_total': invoice.total_amount,
        'prior_credited': Decimal(payload['prior_credited']),
        'max_credit': Decimal(payload['max_credit']),
        'remaining_invoice_value': Decimal(payload['remaining_invoice_value']),
        'invoice_line_rows': line_rows,
    }


def _invoice_line_rows(invoice, exclude_credit_note_pk=None):
    rows = []
    for item in invoice.items.all():
        remaining = CreditNoteLine.remaining_quantity(item, exclude_credit_note_pk)
        if remaining <= 0:
            continue
        gross = remaining * item.unit_price
        if item.is_vat_inclusive and item.vat_rate > 0:
            divisor = 1 + (item.vat_rate / Decimal('100'))
            line_total = (gross / divisor).quantize(Decimal('0.01'))
            line_vat = (gross - line_total).quantize(Decimal('0.01'))
        else:
            line_total = gross
            line_vat = (line_total * (item.vat_rate / Decimal('100'))).quantize(Decimal('0.01'))
        rows.append({
            'invoice_line_id': item.pk,
            'description': item.description,
            'quantity': remaining,
            'max_quantity': remaining,
            'unit_price': item.unit_price,
            'vat_rate': item.vat_rate,
            'is_vat_inclusive': item.is_vat_inclusive,
            'line_total': line_total,
            'line_vat': line_vat,
        })
    return rows


def _is_late(issue_date, trigger_event_date):
    if issue_date and trigger_event_date:
        return (issue_date - trigger_event_date).days > 14
    return False


def _save_credit_note_lines(credit_note, post_data, exclude_credit_note_pk=None):
    credit_note.lines.all().delete()
    total_forms = int(post_data.get('lines-TOTAL_FORMS', 0))
    saved = 0
    for i in range(total_forms):
        if post_data.get(f'lines-{i}-DELETE') in ('on', 'true', '1'):
            continue
        invoice_line_id = post_data.get(f'lines-{i}-invoice_line')
        quantity = post_data.get(f'lines-{i}-quantity')
        if not invoice_line_id or not quantity:
            continue
        invoice_line = get_object_or_404(InvoiceItem, pk=invoice_line_id)
        qty = Decimal(quantity)
        remaining = CreditNoteLine.remaining_quantity(invoice_line, exclude_credit_note_pk)
        if qty <= 0 or qty > remaining:
            raise ValidationError(
                f'Invalid quantity for line "{invoice_line.description}" (max {remaining}).'
            )
        CreditNoteLine.objects.create(
            credit_note=credit_note,
            invoice_line=invoice_line,
            description=post_data.get(f'lines-{i}-description') or invoice_line.description,
            quantity=qty,
            unit_price=invoice_line.unit_price,
            vat_rate=invoice_line.vat_rate,
        )
        saved += 1
    if saved == 0:
        raise ValidationError('At least one line item is required.')
    return saved


def _credit_note_edit_rows(credit_note):
    rows = []
    for line in credit_note.lines.select_related('invoice_line'):
        item = line.invoice_line
        posted_other = CreditNoteLine.posted_quantity_for_invoice_line(
            item, exclude_credit_note_pk=credit_note.pk
        )
        max_qty = item.quantity - posted_other
        rows.append({
            'invoice_line_id': item.pk,
            'description': line.description,
            'quantity': line.quantity,
            'max_quantity': max_qty,
            'unit_price': line.unit_price,
            'vat_rate': line.vat_rate,
            'is_vat_inclusive': item.is_vat_inclusive,
            'line_total': line.line_total,
            'line_vat': line.line_vat,
        })
    return rows


class CreditNoteCreateView(CreatePermissionMixin, CreateView):
    model = CreditNote
    form_class = CreditNoteForm
    template_name = 'sales/credit_note_form.html'
    module_name = 'sales'

    def get_initial(self):
        initial = super().get_initial()
        initial.setdefault('issue_date', date.today())
        initial.setdefault('trigger_event_date', date.today())
        invoice_id = self.request.GET.get('invoice')
        if invoice_id:
            invoice = Invoice.objects.filter(
                pk=invoice_id,
                is_active=True,
                status__in=CreditNote.CREDITABLE_INVOICE_STATUSES,
            ).first()
            if invoice:
                initial['original_invoice'] = invoice.pk
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Create Tax Credit Note'
        context['fta_late_warning'] = FTA_LATE_WARNING
        invoice = None
        if self.request.POST.get('original_invoice'):
            invoice = Invoice.objects.filter(pk=self.request.POST.get('original_invoice')).first()
        elif self.request.GET.get('invoice'):
            invoice = Invoice.objects.filter(pk=self.request.GET.get('invoice')).first()

        if invoice:
            context.update(_credit_note_invoice_context(invoice))
        else:
            context['invoice_line_rows'] = []

        form = context.get('form') or self.get_form()
        issue = form.initial.get('issue_date') or (form['issue_date'].value() if form.is_bound else None)
        trigger = form.initial.get('trigger_event_date') or (form['trigger_event_date'].value() if form.is_bound else None)
        if issue and trigger:
            try:
                from datetime import datetime
                idate = issue if hasattr(issue, 'day') else datetime.strptime(str(issue), '%Y-%m-%d').date()
                tdate = trigger if hasattr(trigger, 'day') else datetime.strptime(str(trigger), '%Y-%m-%d').date()
                context['show_late_warning'] = _is_late(idate, tdate)
            except ValueError:
                context['show_late_warning'] = False
        else:
            context['show_late_warning'] = False
        return context

    def post(self, request, *args, **kwargs):
        self.object = None
        form = self.get_form()
        if form.is_valid():
            try:
                return self.form_valid(form)
            except ValidationError as exc:
                messages.error(request, str(exc))
        return self.render_to_response(self.get_context_data(form=form))

    @transaction.atomic
    def form_valid(self, form):
        cn = form.save(commit=False)
        cn.customer = cn.original_invoice.customer
        cn.customer_trn = cn.original_invoice.customer.trn or ''
        cn.created_by = self.request.user
        cn.save()
        _save_credit_note_lines(cn, self.request.POST)
        cn.calculate_totals()
        cn.validate_totals()
        if cn.late_issuance:
            messages.warning(self.request, FTA_LATE_WARNING)
        messages.success(self.request, f'Tax Credit Note {cn.number} created.')
        return redirect('sales:credit_note_detail', pk=cn.pk)


class CreditNoteUpdateView(UpdatePermissionMixin, UpdateView):
    model = CreditNote
    form_class = CreditNoteForm
    template_name = 'sales/credit_note_form.html'
    module_name = 'sales'

    def get_queryset(self):
        return CreditNote.objects.filter(is_active=True, status='draft')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Edit Credit Note: {self.object.number}'
        context['fta_late_warning'] = FTA_LATE_WARNING
        invoice = self.object.original_invoice
        context.update(_credit_note_invoice_context(invoice, exclude_credit_note_pk=self.object.pk))
        context['invoice_line_rows'] = _credit_note_edit_rows(self.object)
        context['show_late_warning'] = self.object.late_issuance
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        if form.is_valid():
            try:
                return self.form_valid(form)
            except ValidationError as exc:
                messages.error(request, str(exc))
        return self.render_to_response(self.get_context_data(form=form))

    @transaction.atomic
    def form_valid(self, form):
        cn = form.save()
        _save_credit_note_lines(cn, self.request.POST, exclude_credit_note_pk=cn.pk)
        cn.calculate_totals()
        cn.validate_totals()
        if cn.late_issuance:
            messages.warning(self.request, FTA_LATE_WARNING)
        messages.success(self.request, f'Tax Credit Note {cn.number} updated.')
        return redirect('sales:credit_note_detail', pk=cn.pk)


class CreditNoteDetailView(PermissionRequiredMixin, DetailView):
    model = CreditNote
    template_name = 'sales/credit_note_detail.html'
    context_object_name = 'credit_note'
    module_name = 'sales'
    permission_type = 'view'

    def get_queryset(self):
        return CreditNote.objects.filter(is_active=True).select_related(
            'customer', 'original_invoice', 'journal_entry', 'approved_by', 'created_by'
        ).prefetch_related('lines__invoice_line', 'journal_entry__lines__account')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cn = self.object
        context['title'] = f'Tax Credit Note: {cn.number}'
        context['fta_late_warning'] = FTA_LATE_WARNING
        has_edit = (
            self.request.user.is_superuser
            or PermissionChecker.has_permission(self.request.user, 'sales', 'edit')
        )
        context['can_edit'] = has_edit and cn.status == 'draft'
        context['can_approve'] = has_edit and cn.status == 'draft'
        context['can_post'] = has_edit and cn.status == 'approved'
        prior = CreditNote.posted_total_for_invoice(
            cn.original_invoice,
            exclude_pk=cn.pk if cn.status == 'posted' else None,
        )
        context['prior_credited'] = prior
        context['original_invoice_total'] = cn.original_invoice.total_amount
        return context


@login_required
def invoice_credit_note_data_json(request, pk):
    """JSON payload for credit note line population (direct create + invoice detail)."""
    if not (
        request.user.is_superuser
        or PermissionChecker.has_permission(request.user, 'sales', 'view')
    ):
        return JsonResponse({'error': 'Permission denied.'}, status=403)

    invoice = get_object_or_404(Invoice, pk=pk, is_active=True)
    if invoice.status not in CreditNote.CREDITABLE_INVOICE_STATUSES:
        return JsonResponse({'error': 'Invoice is not eligible for credit notes.'}, status=400)

    exclude_pk = request.GET.get('exclude_credit_note')
    exclude_credit_note_pk = int(exclude_pk) if exclude_pk and exclude_pk.isdigit() else None
    return JsonResponse(_credit_note_invoice_payload(invoice, exclude_credit_note_pk))


@login_required
def invoice_credit_note_lines_json(request, pk):
    """Backward-compatible alias for invoice_credit_note_data_json."""
    return invoice_credit_note_data_json(request, pk)


@login_required
def credit_note_approve(request, pk):
    cn = get_object_or_404(CreditNote, pk=pk, is_active=True)
    if not (request.user.is_superuser or PermissionChecker.has_permission(request.user, 'sales', 'edit')):
        messages.error(request, 'Permission denied.')
        return redirect('sales:credit_note_list')
    if cn.status != 'draft':
        messages.error(request, 'Only draft credit notes can be approved.')
        return redirect('sales:credit_note_detail', pk=pk)
    try:
        cn.validate_totals()
    except ValidationError as exc:
        messages.error(request, str(exc))
        return redirect('sales:credit_note_detail', pk=pk)
    cn.status = 'approved'
    cn.approved_by = request.user
    cn.approved_at = timezone.now()
    cn._update_remaining_invoice_value()
    cn.save()
    if cn.late_issuance:
        messages.warning(request, FTA_LATE_WARNING)
    messages.success(request, f'Tax Credit Note {cn.number} approved.')
    return redirect('sales:credit_note_detail', pk=pk)


@login_required
def credit_note_post(request, pk):
    cn = get_object_or_404(CreditNote, pk=pk, is_active=True)
    if not (request.user.is_superuser or PermissionChecker.has_permission(request.user, 'sales', 'edit')):
        messages.error(request, 'Permission denied.')
        return redirect('sales:credit_note_list')
    try:
        journal = cn.post_to_accounting(user=request.user)
        if cn.late_issuance:
            messages.warning(request, FTA_LATE_WARNING)
        messages.success(
            request,
            f'Tax Credit Note {cn.number} posted. Journal: {journal.entry_number}',
        )
    except ValidationError as exc:
        messages.error(request, str(exc))
    except Exception as exc:
        messages.error(request, f'Error posting credit note: {exc}')
    return redirect('sales:credit_note_detail', pk=pk)


@login_required
def credit_note_pdf(request, pk):
    cn = get_object_or_404(
        CreditNote.objects.select_related('customer', 'original_invoice').prefetch_related('lines'),
        pk=pk,
        is_active=True,
    )
    if not (request.user.is_superuser or PermissionChecker.has_permission(request.user, 'sales', 'view')):
        messages.error(request, 'Permission denied.')
        return redirect('sales:credit_note_list')

    company = CompanySettings.get_settings()
    prior = CreditNote.posted_total_for_invoice(
        cn.original_invoice,
        exclude_pk=cn.pk if cn.status == 'posted' else None,
    )
    context = {
        'credit_note': cn,
        'company': company,
        'prior_credited': prior,
        'original_invoice_total': cn.original_invoice.total_amount,
    }

    if request.GET.get('format') == 'pdf':
        try:
            from weasyprint import HTML
            html = render(request, 'sales/credit_note_pdf.html', context).content.decode('utf-8')
            pdf = HTML(string=html, base_url=request.build_absolute_uri('/')).write_pdf()
            response = HttpResponse(pdf, content_type='application/pdf')
            response['Content-Disposition'] = f'inline; filename="{cn.number}.pdf"'
            return response
        except Exception:
            messages.warning(request, 'PDF generation unavailable; showing print view.')

    return render(request, 'sales/credit_note_pdf.html', context)
