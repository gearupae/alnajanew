"""Purchase Debit Note views."""
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.core.mixins import CreatePermissionMixin, PermissionRequiredMixin, UpdatePermissionMixin
from apps.core.utils import PermissionChecker
from apps.settings_app.models import CompanySettings

from .forms import DebitNoteForm, DebitNoteLineFormSet
from .models import DebitNote, DebitNoteLine, VendorBill, VendorBillItem


class DebitNoteListView(PermissionRequiredMixin, ListView):
    model = DebitNote
    template_name = 'purchase/debit_note_list.html'
    context_object_name = 'debit_notes'
    module_name = 'purchase'
    permission_type = 'view'
    paginate_by = 25

    def get_queryset(self):
        qs = DebitNote.objects.filter(is_active=True).select_related(
            'vendor', 'original_bill', 'journal_entry'
        )
        search = self.request.GET.get('search')
        if search:
            qs = qs.filter(
                Q(number__icontains=search)
                | Q(vendor__name__icontains=search)
                | Q(vendor_credit_note_ref__icontains=search)
                | Q(original_bill__bill_number__icontains=search)
            )
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Debit Notes'
        context['status_choices'] = DebitNote.STATUS_CHOICES
        context['can_create'] = (
            self.request.user.is_superuser
            or PermissionChecker.has_permission(self.request.user, 'purchase', 'create')
        )
        context['can_edit'] = (
            self.request.user.is_superuser
            or PermissionChecker.has_permission(self.request.user, 'purchase', 'edit')
        )
        return context


def _bill_line_rows(bill, exclude_debit_note_pk=None):
    rows = []
    for item in bill.items.all():
        remaining = DebitNoteLine.remaining_quantity(item, exclude_debit_note_pk)
        if remaining <= 0:
            continue
        line_total = remaining * item.unit_price
        line_vat = line_total * (item.vat_rate / Decimal('100'))
        rows.append({
            'bill_line': item,
            'bill_line_id': item.pk,
            'description': item.description,
            'quantity': remaining,
            'max_quantity': remaining,
            'unit_price': item.unit_price,
            'vat_rate': item.vat_rate,
            'line_total': line_total.quantize(Decimal('0.01')),
            'line_vat': line_vat.quantize(Decimal('0.01')),
        })
    return rows


def _save_debit_note_lines(debit_note, post_data, exclude_debit_note_pk=None):
    debit_note.lines.all().delete()
    total_forms = int(post_data.get('lines-TOTAL_FORMS', 0))
    saved = 0
    for i in range(total_forms):
        if post_data.get(f'lines-{i}-DELETE') in ('on', 'true', '1'):
            continue
        bill_line_id = post_data.get(f'lines-{i}-bill_line')
        quantity = post_data.get(f'lines-{i}-quantity')
        if not bill_line_id or not quantity:
            continue
        bill_line = get_object_or_404(VendorBillItem, pk=bill_line_id)
        qty = Decimal(quantity)
        remaining = DebitNoteLine.remaining_quantity(bill_line, exclude_debit_note_pk)
        if qty <= 0 or qty > remaining:
            raise ValidationError(
                f'Invalid quantity for line "{bill_line.description}" (max {remaining}).'
            )
        DebitNoteLine.objects.create(
            debit_note=debit_note,
            bill_line=bill_line,
            description=post_data.get(f'lines-{i}-description') or bill_line.description,
            quantity=qty,
            unit_price=bill_line.unit_price,
            vat_rate=bill_line.vat_rate,
        )
        saved += 1
    if saved == 0:
        raise ValidationError('At least one line item is required.')
    return saved


class DebitNoteCreateView(CreatePermissionMixin, CreateView):
    model = DebitNote
    form_class = DebitNoteForm
    template_name = 'purchase/debit_note_form.html'
    module_name = 'purchase'

    def get_initial(self):
        initial = super().get_initial()
        initial.setdefault('issue_date', date.today())
        initial.setdefault('vendor_credit_note_date', date.today())
        bill_id = self.request.GET.get('bill')
        if bill_id:
            bill = VendorBill.objects.filter(
                pk=bill_id,
                is_active=True,
                status__in=DebitNote.DEBITABLE_BILL_STATUSES,
            ).first()
            if bill:
                initial['original_bill'] = bill.pk
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Create Debit Note'
        context['today'] = date.today().isoformat()
        bill = None
        if self.request.POST.get('original_bill'):
            bill = VendorBill.objects.filter(pk=self.request.POST.get('original_bill')).first()
        elif self.request.GET.get('bill'):
            bill = VendorBill.objects.filter(pk=self.request.GET.get('bill')).first()
        elif self.object and self.object.original_bill_id:
            bill = self.object.original_bill

        if 'lines_formset' not in context:
            if self.object and self.object.pk:
                context['lines_formset'] = DebitNoteLineFormSet(
                    self.request.POST or None,
                    instance=self.object,
                    prefix='lines',
                )
            else:
                context['lines_formset'] = None
        if bill:
            context['selected_bill'] = bill
            context['vendor_name'] = bill.vendor.name
            context['vendor_trn'] = bill.vendor.trn
            context['bill_total'] = bill.total_amount
            prior = DebitNote.posted_total_for_bill(bill)
            context['prior_debited'] = prior
            context['max_debit'] = bill.total_amount - prior
            context['bill_line_rows'] = _bill_line_rows(bill)
        else:
            context['bill_line_rows'] = []
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
        dn = form.save(commit=False)
        dn.vendor = dn.original_bill.vendor
        dn.vendor_trn = dn.original_bill.vendor.trn or ''
        dn.created_by = self.request.user
        dn.save()
        _save_debit_note_lines(dn, self.request.POST)
        dn.calculate_totals()
        dn.validate_totals()
        messages.success(self.request, f'Debit Note {dn.number} created.')
        return redirect('purchase:debit_note_detail', pk=dn.pk)


class DebitNoteUpdateView(UpdatePermissionMixin, UpdateView):
    model = DebitNote
    form_class = DebitNoteForm
    template_name = 'purchase/debit_note_form.html'
    module_name = 'purchase'

    def get_queryset(self):
        return DebitNote.objects.filter(is_active=True, status='draft')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Edit Debit Note: {self.object.number}'
        bill = self.object.original_bill
        context['selected_bill'] = bill
        context['vendor_name'] = bill.vendor.name
        context['vendor_trn'] = bill.vendor.trn
        context['bill_total'] = bill.total_amount
        prior = DebitNote.posted_total_for_bill(bill, exclude_pk=self.object.pk)
        context['prior_debited'] = prior
        context['max_debit'] = bill.total_amount - prior
        context['bill_line_rows'] = _bill_line_rows(bill, exclude_debit_note_pk=self.object.pk)
        if 'lines_formset' not in context:
            context['lines_formset'] = DebitNoteLineFormSet(
                self.request.POST or None,
                instance=self.object,
                prefix='lines',
            )
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
        dn = form.save()
        _save_debit_note_lines(dn, self.request.POST, exclude_debit_note_pk=dn.pk)
        dn.calculate_totals()
        dn.validate_totals()
        messages.success(self.request, f'Debit Note {dn.number} updated.')
        return redirect('purchase:debit_note_detail', pk=dn.pk)


class DebitNoteDetailView(PermissionRequiredMixin, DetailView):
    model = DebitNote
    template_name = 'purchase/debit_note_detail.html'
    context_object_name = 'debit_note'
    module_name = 'purchase'
    permission_type = 'view'

    def get_queryset(self):
        return DebitNote.objects.filter(is_active=True).select_related(
            'vendor', 'original_bill', 'journal_entry', 'approved_by', 'created_by'
        ).prefetch_related('lines__bill_line', 'journal_entry__lines__account')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        dn = self.object
        context['title'] = f'Debit Note: {dn.number}'
        has_edit = (
            self.request.user.is_superuser
            or PermissionChecker.has_permission(self.request.user, 'purchase', 'edit')
        )
        context['can_edit'] = has_edit and dn.status == 'draft'
        context['can_approve'] = has_edit and dn.status == 'draft'
        context['can_post'] = has_edit and dn.status == 'approved'
        prior = DebitNote.posted_total_for_bill(dn.original_bill, exclude_pk=dn.pk if dn.status == 'posted' else None)
        context['prior_debited'] = prior
        context['original_bill_total'] = dn.original_bill.total_amount
        return context


@login_required
def bill_debit_note_lines_json(request, pk):
    """Return bill lines with remaining debitable quantities for DN create form."""
    bill = get_object_or_404(VendorBill, pk=pk, is_active=True)
    if bill.status not in DebitNote.DEBITABLE_BILL_STATUSES:
        return JsonResponse({'error': 'Bill is not eligible for debit notes.'}, status=400)

    lines = []
    for item in bill.items.all():
        remaining = DebitNoteLine.remaining_quantity(item)
        if remaining <= 0:
            continue
        line_total = remaining * item.unit_price
        line_vat = line_total * (item.vat_rate / Decimal('100'))
        lines.append({
            'bill_line_id': item.pk,
            'description': item.description,
            'quantity': str(remaining),
            'max_quantity': str(remaining),
            'unit_price': str(item.unit_price),
            'vat_rate': str(item.vat_rate),
            'line_total': str(line_total.quantize(Decimal('0.01'))),
            'line_vat': str(line_vat.quantize(Decimal('0.01'))),
        })

    prior = DebitNote.posted_total_for_bill(bill)
    return JsonResponse({
        'bill_number': bill.bill_number,
        'vendor_name': bill.vendor.name,
        'vendor_trn': bill.vendor.trn or '',
        'bill_total': str(bill.total_amount),
        'prior_debited': str(prior),
        'max_debit': str(bill.total_amount - prior),
        'lines': lines,
    })


@login_required
def debit_note_approve(request, pk):
    dn = get_object_or_404(DebitNote, pk=pk, is_active=True)
    if not (request.user.is_superuser or PermissionChecker.has_permission(request.user, 'purchase', 'edit')):
        messages.error(request, 'Permission denied.')
        return redirect('purchase:debit_note_list')
    if dn.status != 'draft':
        messages.error(request, 'Only draft debit notes can be approved.')
        return redirect('purchase:debit_note_detail', pk=pk)
    try:
        dn.validate_totals()
    except ValidationError as exc:
        messages.error(request, str(exc))
        return redirect('purchase:debit_note_detail', pk=pk)
    dn.status = 'approved'
    dn.approved_by = request.user
    dn.approved_at = timezone.now()
    dn._update_remaining_bill_value()
    dn.save()
    messages.success(request, f'Debit Note {dn.number} approved.')
    return redirect('purchase:debit_note_detail', pk=pk)


@login_required
def debit_note_post(request, pk):
    dn = get_object_or_404(DebitNote, pk=pk, is_active=True)
    if not (request.user.is_superuser or PermissionChecker.has_permission(request.user, 'purchase', 'edit')):
        messages.error(request, 'Permission denied.')
        return redirect('purchase:debit_note_list')
    try:
        journal = dn.post_to_accounting(user=request.user)
        messages.success(
            request,
            f'Debit Note {dn.number} posted. Journal: {journal.entry_number}',
        )
    except ValidationError as exc:
        messages.error(request, str(exc))
    except Exception as exc:
        messages.error(request, f'Error posting debit note: {exc}')
    return redirect('purchase:debit_note_detail', pk=pk)


@login_required
def debit_note_pdf(request, pk):
    dn = get_object_or_404(
        DebitNote.objects.select_related('vendor', 'original_bill').prefetch_related('lines'),
        pk=pk,
        is_active=True,
    )
    if not (request.user.is_superuser or PermissionChecker.has_permission(request.user, 'purchase', 'view')):
        messages.error(request, 'Permission denied.')
        return redirect('purchase:debit_note_list')

    company = CompanySettings.get_settings()
    prior = DebitNote.posted_total_for_bill(dn.original_bill, exclude_pk=dn.pk if dn.status == 'posted' else None)
    context = {
        'debit_note': dn,
        'company': company,
        'prior_debited': prior,
        'original_bill_total': dn.original_bill.total_amount,
    }

    if request.GET.get('format') == 'pdf':
        try:
            from weasyprint import HTML
            html = render(request, 'purchase/debit_note_pdf.html', context).content.decode('utf-8')
            pdf = HTML(string=html, base_url=request.build_absolute_uri('/')).write_pdf()
            response = HttpResponse(pdf, content_type='application/pdf')
            response['Content-Disposition'] = f'inline; filename="{dn.number}.pdf"'
            return response
        except Exception:
            messages.warning(request, 'PDF generation unavailable; showing print view.')

    return render(request, 'purchase/debit_note_pdf.html', context)
