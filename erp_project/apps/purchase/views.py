"""
Purchase Views - Vendors, Purchase Requests, Purchase Orders, Vendor Bills, Expense Claims, Recurring Expenses
All purchase transactions post to accounting module as single source of truth.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import ListView, CreateView, UpdateView, DetailView
from django.urls import reverse, reverse_lazy
from django.db.models import Q, Sum, Prefetch
from django.core.exceptions import ValidationError
from django.http import JsonResponse, HttpResponse
from django.utils.dateparse import parse_date
from django.utils import timezone

from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
import json

from django.views.decorators.http import require_POST

from .models import (
    Vendor, PurchaseRequest, PurchaseRequestItem, PurchaseRequestAttachment,
    PurchaseOrder, PurchaseOrderItem, PurchaseOrderReceipt, PurchaseOrderReceiptLine,
    VendorBill, VendorBillItem, VendorBillAttachment,
    ExpenseClaim, ExpenseClaimItem, RecurringExpense, RecurringExpenseLog,
    DebitNote,
)
from .forms import (
    VendorForm, PurchaseRequestForm, PurchaseRequestItemFormSet,
    PurchaseOrderForm, PurchaseOrderItemFormSet,
    VendorBillForm, VendorBillItemFormSet,
    ExpenseClaimForm, ExpenseClaimItemFormSet, ExpenseClaimPaymentForm,
    RecurringExpenseForm
)
from .pr_approval_rules import annotate_pr_approval_actions, user_can_act_on_purchase_request
from apps.core.mixins import PermissionRequiredMixin, CreatePermissionMixin, UpdatePermissionMixin
from apps.core.utils import PermissionChecker


def _active_inventory_items_data():
    """Active inventory items for PR/PO line dropdowns (embedded in forms)."""
    from apps.inventory.models import Item
    from apps.inventory.serial_stock import annotate_item_available_stock

    rows = annotate_item_available_stock(
        Item.objects.filter(is_active=True, status='active')
    ).order_by('name')
    return [
        {
            'id': r.pk,
            'label': str(r),
            'unit': (r.unit or 'pcs').strip(),
            'purchase_price': str(r.purchase_price),
            'current_stock': str(r.total_stock_calc or Decimal('0.00')),
        }
        for r in rows
    ]


def _active_inventory_items_json():
    return json.dumps(_active_inventory_items_data())


def _pr_inventory_items_json():
    return _active_inventory_items_json()


def _save_vendor_bill_attachments(request, bill):
    """Persist uploaded files from `attachments` multi-file input."""
    uploaded = request.FILES.getlist('attachments')
    if not uploaded:
        return
    for f in uploaded:
        VendorBillAttachment.objects.create(
            vendor_bill=bill,
            file=f,
            filename=getattr(f, 'name', '') or '',
            uploaded_by=request.user if request.user.is_authenticated else None,
        )


def _can_manage_pr_vendor_attachments(user, pr) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if pr.requested_by_id == user.id:
        return True
    return PermissionChecker.has_permission(user, 'purchase', 'edit')


def _pr_vendor_quotes_context(request, pr):
    """Shared context for vendor quote UI on PR detail and edit pages."""
    _ph = 999_999_999
    return {
        'can_manage_vendor_quotes': _can_manage_pr_vendor_attachments(request.user, pr),
        'quote_attachments': pr.attachments.select_related('vendor_ref').order_by('id'),
        'vendor_choices': Vendor.objects.filter(is_active=True).order_by('name'),
        'pr_vendor_add_url': reverse('purchase:pr_vendor_add', args=[pr.pk]),
        'pr_vendor_upload_url': reverse('purchase:pr_vendor_attachment_upload', args=[pr.pk]),
        'pr_vendor_update_url_pattern': reverse(
            'purchase:pr_vendor_attachment_update',
            args=[pr.pk, _ph],
        ).replace(str(_ph), '__ATT_ID__'),
    }


def _serialize_pr_vendor_attachment(att):
    name = att.filename or ''
    if not name and att.file:
        name = Path(att.file.name).name
    vendor_id = att.vendor_ref_id or ''
    vendor_label = att.vendor_display if att.vendor_ref_id or att.vendor else ''
    return {
        'id': att.pk,
        'vendor_id': vendor_id,
        'vendor': att.vendor or '',
        'vendor_label': vendor_label,
        'total_price': str(att.total_price) if att.total_price is not None else '',
        'filename': name,
        'file_url': att.file.url if att.file else '',
        'has_file': bool(att.file),
    }


# ============ VENDOR VIEWS ============

class VendorListView(PermissionRequiredMixin, ListView):
    model = Vendor
    template_name = 'purchase/vendor_list.html'
    context_object_name = 'vendors'
    module_name = 'purchase'
    permission_type = 'view'
    paginate_by = 25
    
    def get_queryset(self):
        queryset = Vendor.objects.filter(is_active=True).order_by('-created_at', '-pk')
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(vendor_number__icontains=search) |
                Q(email__icontains=search)
            )
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Vendors'
        context['form'] = VendorForm()
        context['can_create'] = self.request.user.is_superuser or PermissionChecker.has_permission(self.request.user, 'purchase', 'create')
        context['can_edit'] = self.request.user.is_superuser or PermissionChecker.has_permission(self.request.user, 'purchase', 'edit')
        context['can_delete'] = self.request.user.is_superuser or PermissionChecker.has_permission(self.request.user, 'purchase', 'delete')
        
        # Calculate metrics
        all_vendors = Vendor.objects.filter(is_active=True)
        context['total_vendors'] = all_vendors.count()
        context['active_vendors'] = all_vendors.filter(status='active').count()
        context['total_pos'] = PurchaseOrder.objects.filter(is_active=True, vendor__is_active=True).count()
        
        return context
    
    def post(self, request, *args, **kwargs):
        if not (request.user.is_superuser or PermissionChecker.has_permission(request.user, 'purchase', 'create')):
            messages.error(request, 'Permission denied.')
            return redirect('purchase:vendor_list')
        
        form = VendorForm(request.POST)
        if form.is_valid():
            vendor = form.save()
            messages.success(request, f'Vendor {vendor.name} created successfully.')
            return redirect('purchase:vendor_list')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
        return redirect('purchase:vendor_list')


class VendorUpdateView(UpdatePermissionMixin, UpdateView):
    model = Vendor
    form_class = VendorForm
    template_name = 'purchase/vendor_form.html'
    success_url = reverse_lazy('purchase:vendor_list')
    module_name = 'purchase'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Edit Vendor: {self.object.name}'
        return context
    
    def form_valid(self, form):
        messages.success(self.request, f'Vendor {form.instance.name} updated successfully.')
        return super().form_valid(form)


@login_required
def vendor_delete(request, pk):
    vendor = get_object_or_404(Vendor, pk=pk)
    if request.user.is_superuser or PermissionChecker.has_permission(request.user, 'purchase', 'delete'):
        vendor.is_active = False
        vendor.save()
        messages.success(request, f'Vendor {vendor.name} deleted.')
    else:
        messages.error(request, 'Permission denied.')
    return redirect('purchase:vendor_list')


# ============ PURCHASE REQUEST VIEWS ============

class PurchaseRequestListView(PermissionRequiredMixin, ListView):
    model = PurchaseRequest
    template_name = 'purchase/pr_list.html'
    context_object_name = 'purchase_requests'
    module_name = 'purchase'
    permission_type = 'view'
    paginate_by = 25
    
    def get_queryset(self):
        queryset = PurchaseRequest.objects.filter(is_active=True).select_related(
            'requested_by', 'created_by'
        )
        from apps.core.visibility import filter_purchase_requests_for_user

        queryset = filter_purchase_requests_for_user(queryset, self.request.user)
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(pr_number__icontains=search)
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Purchase Requests'
        context['status_choices'] = PurchaseRequest.STATUS_CHOICES
        context['can_create'] = self.request.user.is_superuser or PermissionChecker.has_permission(self.request.user, 'purchase', 'create')
        context['can_edit'] = self.request.user.is_superuser or PermissionChecker.has_permission(self.request.user, 'purchase', 'edit')
        context['can_delete'] = self.request.user.is_superuser or PermissionChecker.has_permission(self.request.user, 'purchase', 'delete')
        context['can_convert'] = self.request.user.is_superuser or PermissionChecker.has_permission(self.request.user, 'purchase', 'create')
        context['today'] = date.today().isoformat()

        from .pr_approval_rules import (
            annotate_pr_approval_actions,
            pending_purchase_requests_for_user,
            user_is_purchase_request_approver,
        )

        purchase_requests = context.get('purchase_requests')
        if purchase_requests is not None:
            annotate_pr_approval_actions(self.request.user, purchase_requests)

        pending_for_approver = pending_purchase_requests_for_user(self.request.user)
        context['pending_approval_prs'] = pending_for_approver
        context['pending_approval_count'] = len(pending_for_approver)
        context['is_pr_approver'] = user_is_purchase_request_approver(self.request.user)

        return context


class PurchaseRequestCreateView(CreatePermissionMixin, CreateView):
    model = PurchaseRequest
    form_class = PurchaseRequestForm
    template_name = 'purchase/pr_form.html'
    success_url = reverse_lazy('purchase:pr_list')
    module_name = 'purchase'
    
    def get_initial(self):
        initial = super().get_initial()
        sr_id = self.request.GET.get('sr')
        if sr_id:
            initial['service_request'] = sr_id
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Create Purchase Request'
        context['today'] = date.today().isoformat()
        if 'items_formset' not in kwargs:
            if self.request.POST:
                context['items_formset'] = PurchaseRequestItemFormSet(self.request.POST)
            else:
                context['items_formset'] = PurchaseRequestItemFormSet()
        else:
            context['items_formset'] = kwargs['items_formset']
        context['pr_inventory_items_data'] = _active_inventory_items_data()
        context['pr_inventory_items_json'] = json.dumps(context['pr_inventory_items_data'])
        context['preselect_sr'] = self.request.GET.get('sr')
        return context

    def post(self, request, *args, **kwargs):
        self.object = None
        form = self.get_form()
        items_formset = PurchaseRequestItemFormSet(request.POST)

        if form.is_valid() and items_formset.is_valid():
            return self.form_valid(form, items_formset)
        else:
            return self.form_invalid(form, items_formset)

    def form_valid(self, form, items_formset):
        form.instance.requested_by = self.request.user
        self.object = form.save()
        items_formset.instance = self.object
        items_formset.save()
        self.object.calculate_total()
        # Save attachments
        for f in self.request.FILES.getlist('attachments'):
            PurchaseRequestAttachment.objects.create(
                purchase_request=self.object,
                file=f,
                filename=f.name,
                uploaded_by=self.request.user
            )
        messages.success(self.request, f'Purchase Request {self.object.pr_number} created.')
        return redirect(self.success_url)

    def form_invalid(self, form, items_formset):
        return self.render_to_response(
            self.get_context_data(form=form, items_formset=items_formset)
        )


class PurchaseRequestUpdateView(UpdatePermissionMixin, UpdateView):
    model = PurchaseRequest
    form_class = PurchaseRequestForm
    template_name = 'purchase/pr_form.html'
    module_name = 'purchase'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Edit PR: {self.object.pr_number}'
        context['today'] = date.today().isoformat()
        context['can_convert'] = self.request.user.is_superuser or PermissionChecker.has_permission(self.request.user, 'purchase', 'create')
        if 'items_formset' not in kwargs:
            if self.request.POST:
                context['items_formset'] = PurchaseRequestItemFormSet(self.request.POST, instance=self.object)
            else:
                context['items_formset'] = PurchaseRequestItemFormSet(instance=self.object)
        else:
            context['items_formset'] = kwargs['items_formset']
        context['pr_inventory_items_data'] = _active_inventory_items_data()
        context['pr_inventory_items_json'] = json.dumps(context['pr_inventory_items_data'])
        if self.object and self.object.pk:
            context.update(_pr_vendor_quotes_context(self.request, self.object))
        return context
    
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        items_formset = PurchaseRequestItemFormSet(request.POST, instance=self.object)
        
        if form.is_valid() and items_formset.is_valid():
            return self.form_valid(form, items_formset)
        else:
            return self.form_invalid(form, items_formset)
    
    def form_valid(self, form, items_formset):
        pr = form.save(commit=False)
        if self.object.pk and self.object.status not in ('draft', 'returned'):
            pr.status = self.object.status
        pr.save()
        self.object = pr
        items_formset.instance = self.object
        items_formset.save()
        self.object.calculate_total()
        # Save new attachments
        for f in self.request.FILES.getlist('attachments'):
            PurchaseRequestAttachment.objects.create(
                purchase_request=self.object,
                file=f,
                filename=f.name,
                uploaded_by=self.request.user
            )
        messages.success(self.request, f'Purchase Request {self.object.pr_number} updated.')
        return redirect('purchase:pr_detail', pk=self.object.pk)
    
    def form_invalid(self, form, items_formset):
        return self.render_to_response(
            self.get_context_data(form=form, items_formset=items_formset)
        )


class PurchaseRequestDetailView(PermissionRequiredMixin, DetailView):
    model = PurchaseRequest
    template_name = 'purchase/pr_detail.html'
    context_object_name = 'pr'
    module_name = 'purchase'
    permission_type = 'view'

    def get_queryset(self):
        qs = (
            PurchaseRequest.objects.filter(is_active=True)
            .select_related('requested_by', 'department', 'created_by', 'vendor', 'service_request')
            .prefetch_related('items', 'attachments')
        )
        from apps.core.visibility import filter_purchase_requests_for_user

        return filter_purchase_requests_for_user(qs, self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'PR: {self.object.pr_number}'
        context['can_edit'] = (
            (self.request.user.is_superuser or
             PermissionChecker.has_permission(self.request.user, 'purchase', 'edit'))
            and (self.object.status in ['draft', 'returned'] or
                 (self.request.user.is_superuser and self.object.status == 'approved'))
        )
        context['can_submit'] = context['can_edit'] and self.object.status in ['draft', 'returned']
        can_act = user_can_act_on_purchase_request(self.request.user, self.object)
        context['can_approve'] = can_act
        context['can_reject'] = can_act
        context['can_return'] = can_act
        context['can_convert'] = (
            self.request.user.is_superuser or
            PermissionChecker.has_permission(self.request.user, 'purchase', 'create')
        ) and self.object.status == 'approved'
        from apps.inventory.models import Item
        from apps.inventory.serial_stock import annotate_item_available_stock

        items = list(self.object.items.select_related('inventory_item').all())
        inv_ids = [i.inventory_item_id for i in items if i.inventory_item_id]
        stock_by_id = {}
        if inv_ids:
            for row in annotate_item_available_stock(
                Item.objects.filter(pk__in=inv_ids)
            ).values('pk', 'total_stock_calc'):
                stock_by_id[row['pk']] = row['total_stock_calc']
        for line in items:
            if line.inventory_item_id:
                line.current_stock = stock_by_id.get(line.inventory_item_id, Decimal('0.00'))
            else:
                line.current_stock = None
        context['pr_line_items'] = items
        context.update(_pr_vendor_quotes_context(self.request, self.object))
        return context


@login_required
@require_POST
def pr_vendor_attachment_upload(request, pk):
    """Upload one or more vendor quote files (PDF / Excel) for a purchase request."""
    pr = get_object_or_404(PurchaseRequest, pk=pk, is_active=True)
    if not _can_manage_pr_vendor_attachments(request.user, pr):
        return JsonResponse({'ok': False, 'error': 'Permission denied.'}, status=403)
    allowed_ext = {'.pdf', '.xlsx', '.xls'}
    files = request.FILES.getlist('files')
    if not files:
        return JsonResponse({'ok': False, 'error': 'No files uploaded.'}, status=400)
    for f in files:
        ext = Path(f.name).suffix.lower()
        if ext not in allowed_ext:
            return JsonResponse(
                {
                    'ok': False,
                    'error': (
                        f'File type not allowed: {f.name}. '
                        'Use PDF or Excel (.xlsx, .xls).'
                    ),
                },
                status=400,
            )
    created = []
    for f in files:
        att = PurchaseRequestAttachment.objects.create(
            purchase_request=pr,
            file=f,
            filename=f.name,
            uploaded_by=request.user,
        )
        created.append(att)
    return JsonResponse(
        {
            'ok': True,
            'attachments': [_serialize_pr_vendor_attachment(a) for a in created],
        }
    )


@login_required
@require_POST
def pr_vendor_attachment_update(request, pk, attachment_id):
    """Auto-save vendor name and total price for one attachment (JSON body)."""
    ct = (request.content_type or '').split(';')[0].strip().lower()
    if ct != 'application/json':
        return JsonResponse({'ok': False, 'error': 'Expected application/json.'}, status=400)
    pr = get_object_or_404(PurchaseRequest, pk=pk, is_active=True)
    if not _can_manage_pr_vendor_attachments(request.user, pr):
        return JsonResponse({'ok': False, 'error': 'Permission denied.'}, status=403)
    att = get_object_or_404(PurchaseRequestAttachment, pk=attachment_id, purchase_request=pr)
    try:
        data = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'Invalid JSON.'}, status=400)
    update_fields = []
    if 'vendor_id' in data:
        raw_id = data.get('vendor_id')
        if raw_id in (None, '', 0, '0'):
            att.vendor_ref = None
            update_fields.append('vendor_ref')
        else:
            try:
                vendor = Vendor.objects.filter(pk=int(raw_id), is_active=True).first()
            except (TypeError, ValueError):
                return JsonResponse({'ok': False, 'error': 'Invalid vendor.'}, status=400)
            if not vendor:
                return JsonResponse({'ok': False, 'error': 'Vendor not found.'}, status=400)
            att.vendor_ref = vendor
            att.vendor = vendor.name[:500]
            update_fields.extend(['vendor_ref', 'vendor'])
    elif 'vendor' in data:
        att.vendor = (data.get('vendor') or '')[:500]
        update_fields.append('vendor')
    if 'total_price' in data:
        raw = data.get('total_price')
        if raw is None or raw == '':
            att.total_price = None
        else:
            try:
                att.total_price = Decimal(str(raw))
            except (InvalidOperation, TypeError, ValueError):
                return JsonResponse({'ok': False, 'error': 'Invalid total price.'}, status=400)
        update_fields.append('total_price')
    if not update_fields:
        return JsonResponse({'ok': False, 'error': 'No fields to update.'}, status=400)
    att.save(update_fields=update_fields)
    payload = _serialize_pr_vendor_attachment(att)
    payload['ok'] = True
    return JsonResponse(payload)


@login_required
@require_POST
def pr_vendor_add(request, pk):
    """Add a vendor quote row without requiring a file (JSON body)."""
    ct = (request.content_type or '').split(';')[0].strip().lower()
    if ct != 'application/json':
        return JsonResponse({'ok': False, 'error': 'Expected application/json.'}, status=400)
    pr = get_object_or_404(PurchaseRequest, pk=pk, is_active=True)
    if not _can_manage_pr_vendor_attachments(request.user, pr):
        return JsonResponse({'ok': False, 'error': 'Permission denied.'}, status=403)
    try:
        data = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'Invalid JSON.'}, status=400)

    vendor_ref = None
    vendor_name = (data.get('vendor') or '').strip()[:500]
    raw_id = data.get('vendor_id')
    if raw_id not in (None, '', 0, '0'):
        try:
            vendor_ref = Vendor.objects.filter(pk=int(raw_id), is_active=True).first()
        except (TypeError, ValueError):
            return JsonResponse({'ok': False, 'error': 'Invalid vendor.'}, status=400)
        if not vendor_ref:
            return JsonResponse({'ok': False, 'error': 'Vendor not found.'}, status=400)
        vendor_name = vendor_ref.name[:500]
    if not vendor_name:
        return JsonResponse({'ok': False, 'error': 'Select a vendor.'}, status=400)

    total_price = None
    raw_total = data.get('total_price')
    if raw_total not in (None, ''):
        try:
            total_price = Decimal(str(raw_total))
        except (InvalidOperation, TypeError, ValueError):
            return JsonResponse({'ok': False, 'error': 'Invalid total price.'}, status=400)

    att = PurchaseRequestAttachment.objects.create(
        purchase_request=pr,
        vendor_ref=vendor_ref,
        vendor=vendor_name,
        total_price=total_price,
        uploaded_by=request.user,
    )
    payload = _serialize_pr_vendor_attachment(att)
    payload['ok'] = True
    return JsonResponse(payload)


@login_required
def pr_submit(request, pk):
    """Submit purchase request for approval."""
    pr = get_object_or_404(PurchaseRequest, pk=pk)
    
    if pr.status not in ['draft', 'returned']:
        messages.error(request, 'Only draft or returned requests can be submitted.')
        return redirect('purchase:pr_detail', pk=pk)
    
    if pr.items.count() == 0:
        messages.error(request, 'Cannot submit without at least one line item.')
        return redirect('purchase:pr_detail', pk=pk)
    
    pr.status = 'pending'
    pr.rejection_reason = ''
    pr.save()
    
    from apps.settings_app.models import ApprovalConfiguration
    ApprovalConfiguration.notify_approver(pr, 'purchase_request')
    
    from apps.settings_app.models import Notification
    Notification.create(
        user=pr.requested_by,
        title='Purchase Request Submitted',
        message=f'Your Purchase Request {pr.pr_number} has been submitted for approval.',
        link=f'/purchase/requests/{pr.pk}/'
    )
    
    messages.success(request, f'Purchase Request {pr.pr_number} submitted for approval.')
    return redirect('purchase:pr_detail', pk=pk)


@login_required
def pr_approve(request, pk):
    pr = get_object_or_404(PurchaseRequest, pk=pk)
    if pr.status != 'pending':
        messages.error(request, 'Only pending requests can be approved.')
        return redirect('purchase:pr_detail', pk=pk)
    if not user_can_act_on_purchase_request(request.user, pr):
        messages.error(request, 'Only the configured approver can approve this request.')
        return redirect('purchase:pr_detail', pk=pk)
    pr.status = 'approved'
    pr.rejection_reason = ''
    pr.save()
    from apps.settings_app.models import ApprovalAuditLog
    ApprovalAuditLog.objects.create(
        module='purchase_request',
        reference=pr.pr_number,
        approver=request.user,
        action='approve',
        comment=''
    )
    from apps.settings_app.models import Notification
    Notification.create(
        user=pr.requested_by,
        title='Purchase Request Approved',
        message=f'Purchase Request {pr.pr_number} has been approved.',
        link=f'/purchase/requests/{pr.pk}/'
    )
    messages.success(request, f'PR {pr.pr_number} approved.')
    return redirect('purchase:pr_detail', pk=pk)


@login_required
def pr_reject(request, pk):
    pr = get_object_or_404(PurchaseRequest, pk=pk)
    if not user_can_act_on_purchase_request(request.user, pr):
        messages.error(request, 'Only the configured approver can reject this request.')
        return redirect('purchase:pr_list')
    if pr.status != 'pending':
        messages.error(request, 'Only pending requests can be rejected.')
        return redirect('purchase:pr_detail', pk=pk)
    if request.method == 'POST':
        comment = request.POST.get('comment', '').strip()
        pr.status = 'rejected'
        pr.rejection_reason = comment
        pr.save()
        from apps.settings_app.models import ApprovalAuditLog, Notification
        ApprovalAuditLog.objects.create(
            module='purchase_request',
            reference=pr.pr_number,
            approver=request.user,
            action='reject',
            comment=comment
        )
        Notification.create(
            user=pr.requested_by,
            title='Purchase Request Rejected',
            message=f'Purchase Request {pr.pr_number} has been rejected.' + (f' Reason: {comment[:100]}...' if comment else ''),
            link=f'/purchase/requests/{pr.pk}/'
        )
        messages.success(request, f'PR {pr.pr_number} rejected.')
        return redirect('purchase:pr_list')
    return redirect('purchase:pr_detail', pk=pk)


@login_required
def pr_return(request, pk):
    """Return purchase request for revision with comment."""
    pr = get_object_or_404(PurchaseRequest, pk=pk)
    if not user_can_act_on_purchase_request(request.user, pr):
        messages.error(request, 'Only the configured approver can reject this request.')
        return redirect('purchase:pr_list')
    if pr.status != 'pending':
        messages.error(request, 'Only pending requests can be returned.')
        return redirect('purchase:pr_detail', pk=pk)
    if request.method == 'POST':
        comment = request.POST.get('comment', '').strip()
        pr.status = 'returned'
        pr.rejection_reason = comment
        pr.save()
        from apps.settings_app.models import ApprovalAuditLog, Notification
        ApprovalAuditLog.objects.create(
            module='purchase_request',
            reference=pr.pr_number,
            approver=request.user,
            action='return',
            comment=comment
        )
        Notification.create(
            user=pr.requested_by,
            title='Purchase Request Returned for Revision',
            message=f'Purchase Request {pr.pr_number} has been returned for revision. {comment[:100]}{"..." if len(comment) > 100 else ""}',
            link=f'/purchase/requests/{pr.pk}/'
        )
        messages.success(request, f'PR {pr.pr_number} returned for revision.')
        return redirect('purchase:pr_list')
    return redirect('purchase:pr_detail', pk=pk)


@login_required
def pr_delete(request, pk):
    pr = get_object_or_404(PurchaseRequest, pk=pk)
    if request.user.is_superuser or PermissionChecker.has_permission(request.user, 'purchase', 'delete'):
        pr.is_active = False
        pr.save()
        messages.success(request, f'PR {pr.pr_number} deleted.')
    else:
        messages.error(request, 'Permission denied.')
    return redirect('purchase:pr_list')


@login_required
def pr_convert(request, pk):
    """Redirect to PO create with PR pre-selected. Only for approved PRs."""
    pr = get_object_or_404(PurchaseRequest, pk=pk)
    if not (request.user.is_superuser or PermissionChecker.has_permission(request.user, 'purchase', 'create')):
        messages.error(request, 'Permission denied.')
        return redirect('purchase:pr_list')
    if pr.status != 'approved':
        messages.error(request, 'Only approved Purchase Requests can be converted to Purchase Order.')
        return redirect('purchase:pr_detail', pk=pk)
    url = reverse('purchase:po_create') + '?pr=' + str(pr.pk)
    return redirect(url)


@login_required
def pr_items_json(request, pk):
    """Return PR items as JSON for AJAX requests."""
    pr = get_object_or_404(PurchaseRequest, pk=pk)
    items = []
    for item in pr.items.all():
        items.append({
            'description': item.description,
            'quantity': str(item.quantity),
            'estimated_price': str(item.estimated_price),
            # Use estimated_price as unit_price, and default VAT to 5%
            'unit_price': str(item.estimated_price),
            'vat_rate': '5.00',
            'inventory_item_id': item.inventory_item_id,
        })
    return JsonResponse({
        'items': items,
        'vendor_id': pr.vendor_id,
        'service_request_id': pr.service_request_id,
    })


@login_required
def po_items_json(request, pk):
    """Return PO items as JSON for vendor bill / AJAX."""
    from .po_billing import po_items_billing_payload

    po = get_object_or_404(PurchaseOrder.objects.prefetch_related('items'), pk=pk)
    bill_received = request.GET.get('bill_received', '1') != '0'
    exclude_bill_id = request.GET.get('exclude_bill')
    exclude = int(exclude_bill_id) if exclude_bill_id and str(exclude_bill_id).isdigit() else None
    return JsonResponse(
        po_items_billing_payload(
            po,
            bill_received_only=bill_received,
            exclude_bill_id=exclude,
        )
    )


# ============ PURCHASE ORDER VIEWS ============

class PurchaseOrderListView(PermissionRequiredMixin, ListView):
    model = PurchaseOrder
    template_name = 'purchase/po_list.html'
    context_object_name = 'purchase_orders'
    module_name = 'purchase'
    permission_type = 'view'
    paginate_by = 25
    
    def get_queryset(self):
        queryset = PurchaseOrder.objects.filter(is_active=True).select_related(
            'vendor', 'project', 'created_by', 'purchase_request', 'purchase_request__requested_by'
        )
        from apps.core.visibility import filter_purchase_orders_for_user

        queryset = filter_purchase_orders_for_user(queryset, self.request.user)
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(po_number__icontains=search) |
                Q(vendor__name__icontains=search)
            )
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Purchase Orders'
        context['status_choices'] = PurchaseOrder.STATUS_CHOICES
        context['can_create'] = self.request.user.is_superuser or PermissionChecker.has_permission(self.request.user, 'purchase', 'create')
        context['can_edit'] = self.request.user.is_superuser or PermissionChecker.has_permission(self.request.user, 'purchase', 'edit')
        context['can_delete'] = self.request.user.is_superuser or PermissionChecker.has_permission(self.request.user, 'purchase', 'delete')
        context['today'] = date.today().isoformat()
        
        # Calculate metrics
        all_pos = PurchaseOrder.objects.filter(is_active=True)
        context['total_pos'] = all_pos.count()
        context['total_amount'] = all_pos.aggregate(total=Sum('total_amount'))['total'] or 0
        context['pending_pos'] = all_pos.filter(status__in=['draft', 'sent', 'confirmed', 'partial_received']).count()
        context['confirmed_pos'] = all_pos.filter(status='confirmed').count()
        
        return context


class PurchaseOrderCreateView(CreatePermissionMixin, CreateView):
    model = PurchaseOrder
    form_class = PurchaseOrderForm
    template_name = 'purchase/po_form.html'
    success_url = reverse_lazy('purchase:po_list')
    module_name = 'purchase'
    
    def get_initial(self):
        initial = super().get_initial()
        sr_id = self.request.GET.get('sr')
        if sr_id:
            initial['service_request'] = sr_id
        pr_id = self.request.GET.get('pr')
        if pr_id:
            initial['purchase_request'] = pr_id
        return initial

    def get_context_data(self, **kwargs):
        from apps.finance.models import TaxCode
        context = super().get_context_data(**kwargs)
        context['title'] = 'Create Purchase Order'
        context['today'] = date.today().isoformat()
        # Tax Codes for VAT selection (SAP/Oracle Standard)
        context['tax_codes'] = TaxCode.objects.filter(is_active=True).order_by('code')
        context['default_tax_code'] = TaxCode.objects.filter(is_active=True, is_default=True).first()
        context['preselect_pr'] = self.request.GET.get('pr')
        context['preselect_sr'] = self.request.GET.get('sr')
        if 'items_formset' not in kwargs:
            if self.request.POST:
                context['items_formset'] = PurchaseOrderItemFormSet(self.request.POST)
            else:
                context['items_formset'] = PurchaseOrderItemFormSet()
        else:
            context['items_formset'] = kwargs['items_formset']
        context['po_inventory_items_data'] = _active_inventory_items_data()
        context['po_inventory_items_json'] = json.dumps(context['po_inventory_items_data'])
        return context
    
    def post(self, request, *args, **kwargs):
        self.object = None
        form = self.get_form()
        items_formset = PurchaseOrderItemFormSet(request.POST)
        
        if form.is_valid() and items_formset.is_valid():
            return self.form_valid(form, items_formset)
        else:
            return self.form_invalid(form, items_formset)
    
    def form_valid(self, form, items_formset):
        self.object = form.save()
        items_formset.instance = self.object
        items_formset.save()
        self.object.calculate_totals()
        # When PO is created from PR, update PR status to converted
        if self.object.purchase_request:
            self.object.purchase_request.status = 'converted'
            self.object.purchase_request.save(update_fields=['status'])
        # When PO is created from SR, update SR status to converted
        if self.object.service_request:
            self.object.service_request.status = 'converted'
            self.object.service_request.save(update_fields=['status'])
        messages.success(self.request, f'Purchase Order {self.object.po_number} created.')
        return redirect(self.success_url)
    
    def form_invalid(self, form, items_formset):
        return self.render_to_response(
            self.get_context_data(form=form, items_formset=items_formset)
        )


class PurchaseOrderUpdateView(UpdatePermissionMixin, UpdateView):
    model = PurchaseOrder
    form_class = PurchaseOrderForm
    template_name = 'purchase/po_form.html'
    module_name = 'purchase'
    
    def get_context_data(self, **kwargs):
        from apps.finance.models import TaxCode
        context = super().get_context_data(**kwargs)
        context['title'] = f'Edit PO: {self.object.po_number}'
        context['today'] = date.today().isoformat()
        # Tax Codes for VAT selection (SAP/Oracle Standard)
        context['tax_codes'] = TaxCode.objects.filter(is_active=True).order_by('code')
        context['default_tax_code'] = TaxCode.objects.filter(is_active=True, is_default=True).first()
        if 'items_formset' not in kwargs:
            if self.request.POST:
                context['items_formset'] = PurchaseOrderItemFormSet(self.request.POST, instance=self.object)
            else:
                context['items_formset'] = PurchaseOrderItemFormSet(instance=self.object)
        else:
            context['items_formset'] = kwargs['items_formset']
        context['po_inventory_items_data'] = _active_inventory_items_data()
        context['po_inventory_items_json'] = json.dumps(context['po_inventory_items_data'])
        return context
    
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        items_formset = PurchaseOrderItemFormSet(request.POST, instance=self.object)
        
        if form.is_valid() and items_formset.is_valid():
            return self.form_valid(form, items_formset)
        else:
            return self.form_invalid(form, items_formset)
    
    def form_valid(self, form, items_formset):
        self.object = form.save()
        items_formset.instance = self.object
        items_formset.save()
        self.object.calculate_totals()
        messages.success(self.request, f'Purchase Order {self.object.po_number} updated.')
        return redirect('purchase:po_detail', pk=self.object.pk)
    
    def form_invalid(self, form, items_formset):
        return self.render_to_response(
            self.get_context_data(form=form, items_formset=items_formset)
        )


class PurchaseOrderDetailView(PermissionRequiredMixin, DetailView):
    model = PurchaseOrder
    template_name = 'purchase/po_detail.html'
    context_object_name = 'po'
    module_name = 'purchase'
    permission_type = 'view'

    def get_queryset(self):
        rcpt_qs = (
            PurchaseOrderReceipt.objects.select_related('warehouse', 'created_by')
            .prefetch_related(
                Prefetch(
                    'lines',
                    queryset=PurchaseOrderReceiptLine.objects.select_related(
                        'purchase_order_item',
                        'purchase_order_item__inventory_item',
                    ),
                )
            )
            .order_by('created_at')
        )
        qs = (
            PurchaseOrder.objects.filter(is_active=True)
            .select_related('vendor', 'project', 'purchase_request', 'service_request', 'created_by')
            .prefetch_related(
                Prefetch('goods_receipts', queryset=rcpt_qs),
                'items__inventory_item',
                Prefetch(
                    'bills',
                    queryset=VendorBill.objects.filter(is_active=True).order_by('-created_at'),
                ),
            )
        )
        from apps.core.visibility import filter_purchase_orders_for_user

        return filter_purchase_orders_for_user(qs, self.request.user)

    def get_context_data(self, **kwargs):
        from apps.settings_app.models import CompanySettings

        from .email_outbound import outgoing_mail_hint
        from .receiving import purchase_order_can_receive

        context = super().get_context_data(**kwargs)
        context['title'] = f'PO: {self.object.po_number}'
        context['can_edit'] = self.request.user.is_superuser or PermissionChecker.has_permission(self.request.user, 'purchase', 'edit')
        company = CompanySettings.get_settings()
        context['po_email_hint'] = outgoing_mail_hint(company)
        context['can_send_po_email'] = (
            self.request.user.is_superuser
            or PermissionChecker.has_permission(self.request.user, 'purchase', 'edit')
        ) and self.object.status != 'cancelled'
        context['po_email_send_url'] = reverse('purchase:po_send_email', args=[self.object.pk])
        context['po_email_default_subject'] = f'Purchase Order {self.object.po_number}'
        vendor_name = self.object.vendor.name if self.object.vendor_id else 'Vendor'
        context['po_email_default_body'] = (
            f'Dear {vendor_name},\n\n'
            f'Please find attached Purchase Order {self.object.po_number} for your reference.\n\n'
            f'Kind regards,\n{company.company_name}'
        )
        ve = ''
        if self.object.vendor_id and (self.object.vendor.email or '').strip():
            ve = self.object.vendor.email.strip()
        context['po_email_default_to'] = ve

        context['can_receive_po'] = (
            context['can_edit'] and purchase_order_can_receive(self.object)
        )
        context['can_confirm_po'] = (
            context['can_edit']
            and self.object.status == 'draft'
            and self.object.items.exists()
        )
        context['po_receive_url'] = reverse('purchase:po_receive', args=[self.object.pk])

        from apps.inventory.models import Item
        from apps.inventory.serial_stock import annotate_item_available_stock

        items = list(self.object.items.select_related('inventory_item').all())
        inv_ids = [i.inventory_item_id for i in items if i.inventory_item_id]
        stock_by_id = {}
        if inv_ids:
            for row in annotate_item_available_stock(
                Item.objects.filter(pk__in=inv_ids)
            ).values('pk', 'total_stock_calc'):
                stock_by_id[row['pk']] = row['total_stock_calc']
        for line in items:
            if line.inventory_item_id:
                line.current_stock = stock_by_id.get(line.inventory_item_id, Decimal('0.00'))
            else:
                line.current_stock = None
            from .po_billing import annotate_po_item_billing
            annotate_po_item_billing(line)
        context['po_line_items'] = items
        context['po_vendor_bills'] = list(self.object.bills.all())
        context['can_create_bill'] = self.request.user.is_superuser or PermissionChecker.has_permission(
            self.request.user, 'purchase', 'create'
        )
        from .po_billing import po_has_received_items
        context['po_has_received_items'] = po_has_received_items(self.object)
        return context


@login_required
@require_POST
def po_confirm(request, pk):
    """Mark a draft PO as confirmed so goods can be received."""
    po = get_object_or_404(PurchaseOrder.objects.filter(is_active=True), pk=pk)
    if not (request.user.is_superuser or PermissionChecker.has_permission(request.user, 'purchase', 'edit')):
        messages.error(request, 'Permission denied.')
        return redirect('purchase:po_detail', pk=pk)
    if po.status != 'draft':
        messages.warning(request, f'PO {po.po_number} is already {po.get_status_display().lower()}.')
        return redirect('purchase:po_detail', pk=pk)
    if not po.items.exists():
        messages.error(request, 'Add at least one line item before confirming this PO.')
        return redirect('purchase:po_edit', pk=pk)
    po.status = 'confirmed'
    po.save(update_fields=['status', 'updated_at'])
    messages.success(
        request,
        f'PO {po.po_number} confirmed. You can now receive goods into inventory.',
    )
    return redirect('purchase:po_detail', pk=pk)


def _po_receive_line_rows(po, post_data=None):
    """Build template rows with optional reposted qty/price/model numbers."""
    rows = []
    for line in po.items.all():
        if post_data is not None:
            posted_qty = (post_data.get(f'qty_{line.pk}') or '0').strip()
            posted_price = post_data.get(f'price_{line.pk}')
            if posted_price is None or posted_price == '':
                posted_price = f'{line.unit_price:.2f}'
            posted_models = post_data.getlist(f'model_number_{line.pk}')
        else:
            posted_qty = '0'
            posted_price = f'{line.unit_price:.2f}'
            posted_models = []
        rows.append({
            'line': line,
            'posted_qty': posted_qty,
            'posted_price': posted_price,
            'posted_model_numbers': posted_models,
        })
    return rows


def _po_receive_context(po, warehouses, *, post_data=None, warehouse_pk=None, recv_date=None, notes=''):
    if recv_date is None:
        recv_date = timezone.now().date()
    if warehouse_pk is None:
        first_wh = warehouses.first()
        warehouse_pk = first_wh.pk if first_wh else None
    return {
        'title': f'Receive — {po.po_number}',
        'po': po,
        'warehouses': warehouses,
        'receive_lines': _po_receive_line_rows(po, post_data),
        'posted_warehouse_pk': warehouse_pk,
        'posted_received_on': recv_date.isoformat(),
        'posted_notes': notes or '',
    }


@login_required
def po_receive(request, pk):
    """Goods receipt against PO — partial/full receive, stock in, audit trail."""
    from apps.inventory.models import Warehouse

    from .receiving import purchase_order_can_receive, process_goods_receipt

    po = get_object_or_404(
        PurchaseOrder.objects.filter(is_active=True).prefetch_related('items__inventory_item'),
        pk=pk,
    )

    can_edit = request.user.is_superuser or PermissionChecker.has_permission(request.user, 'purchase', 'edit')
    if not can_edit:
        messages.error(request, 'Permission denied.')
        return redirect('purchase:po_detail', pk=pk)

    if not purchase_order_can_receive(po):
        messages.error(request, 'This purchase order cannot receive goods.')
        return redirect('purchase:po_detail', pk=pk)

    warehouses = Warehouse.objects.filter(is_active=True, status='active').order_by('name')

    if request.method == 'POST':
        wid_raw = request.POST.get('warehouse')
        try:
            warehouse_pk = int(wid_raw)
        except (TypeError, ValueError):
            warehouse_pk = None
        recv_date = parse_date(request.POST.get('received_on') or '')
        if not recv_date:
            recv_date = timezone.now().date()
        notes = (request.POST.get('notes') or '').strip()

        payloads = []
        for line in po.items.all():
            payloads.append(
                {
                    'purchase_order_item_id': line.pk,
                    'qty_raw': request.POST.get(f'qty_{line.pk}', ''),
                    'unit_price_raw': request.POST.get(f'price_{line.pk}', ''),
                    'model_numbers': request.POST.getlist(f'model_number_{line.pk}'),
                }
            )

        try:
            process_goods_receipt(
                po.pk,
                warehouse_pk,
                recv_date,
                notes,
                payloads,
                request.user,
            )
        except ValidationError as exc:
            errs = getattr(exc, 'messages', None)
            if errs:
                for msg in errs:
                    messages.error(request, msg)
            else:
                messages.error(request, str(exc))
            return render(
                request,
                'purchase/po_receive.html',
                _po_receive_context(
                    po,
                    warehouses,
                    post_data=request.POST,
                    warehouse_pk=warehouse_pk,
                    recv_date=recv_date,
                    notes=notes,
                ),
            )

        messages.success(request, f'Goods received for PO {po.po_number}. Inventory updated.')
        return redirect('purchase:po_detail', pk=po.pk)

    return render(
        request,
        'purchase/po_receive.html',
        _po_receive_context(po, warehouses),
    )


@login_required
def pr_pdf(request, pk):
    """Purchase request PDF / printable HTML."""
    from .pr_pdf_render import build_pr_pdf_context, render_pr_pdf_bytes
    from apps.core.visibility import filter_purchase_requests_for_user

    pr = get_object_or_404(
        PurchaseRequest.objects.filter(is_active=True)
        .select_related('requested_by', 'department', 'vendor')
        .prefetch_related('items', 'attachments'),
        pk=pk,
    )
    if not filter_purchase_requests_for_user(
        PurchaseRequest.objects.filter(pk=pr.pk), request.user
    ).exists():
        messages.error(request, 'Permission denied.')
        return redirect('purchase:pr_list')

    if not (request.user.is_superuser or PermissionChecker.has_permission(request.user, 'purchase', 'view')):
        messages.error(request, 'Permission denied.')
        return redirect('purchase:pr_list')

    context = build_pr_pdf_context(request, pr)
    output_format = request.GET.get('format', 'html')
    if output_format == 'pdf':
        pdf, err = render_pr_pdf_bytes(request, pr)
        if pdf is not None:
            response = HttpResponse(pdf, content_type='application/pdf')
            response['Content-Disposition'] = f'inline; filename="PR_{pr.pr_number}.pdf"'
            return response
        if err:
            messages.info(request, err)
        return render(request, 'purchase/pr_pdf.html', context)

    return render(request, 'purchase/pr_pdf.html', context)


@login_required
def po_pdf(request, pk):
    """
    Purchase order PDF / printable HTML — same visual design as tax invoice PDF.
    """
    from .po_pdf_render import build_po_pdf_context, render_po_pdf_bytes

    po = get_object_or_404(
        PurchaseOrder.objects.filter(is_active=True)
        .select_related('vendor', 'purchase_request', 'service_request')
        .prefetch_related('items'),
        pk=pk,
    )

    if not (request.user.is_superuser or PermissionChecker.has_permission(request.user, 'purchase', 'view')):
        messages.error(request, 'Permission denied.')
        return redirect('purchase:po_list')

    context = build_po_pdf_context(request, po)

    output_format = request.GET.get('format', 'html')
    if output_format == 'pdf':
        pdf, err = render_po_pdf_bytes(request, po)
        if pdf is not None:
            response = HttpResponse(pdf, content_type='application/pdf')
            response['Content-Disposition'] = f'inline; filename="PO_{po.po_number}.pdf"'
            return response
        if err:
            messages.info(request, err)
        return render(request, 'purchase/po_pdf.html', context)

    return render(request, 'purchase/po_pdf.html', context)


@login_required
@require_POST
def po_send_email(request, pk):
    """Send purchase order by email with PO PDF attached (SMTP from Company Settings or env)."""
    from apps.settings_app.models import CompanySettings

    from .email_outbound import (
        company_outgoing_from_email,
        get_smtp_connection_or_default,
        validate_cc_addresses,
        validate_to_addresses,
    )
    from .po_pdf_render import render_po_pdf_bytes

    if not (request.user.is_superuser or PermissionChecker.has_permission(request.user, 'purchase', 'edit')):
        return JsonResponse({'ok': False, 'error': 'Permission denied.'}, status=403)

    po = get_object_or_404(
        PurchaseOrder.objects.filter(is_active=True)
        .select_related('vendor', 'purchase_request', 'service_request')
        .prefetch_related('items'),
        pk=pk,
    )
    if po.status == 'cancelled':
        return JsonResponse({'ok': False, 'error': 'Cannot email a cancelled purchase order.'}, status=400)

    subject = (request.POST.get('subject') or '').strip()
    body = (request.POST.get('body') or '').strip()
    to_raw = request.POST.get('to', '')
    cc_raw = request.POST.get('cc', '')

    if not subject:
        return JsonResponse({'ok': False, 'error': 'Subject is required.'}, status=400)
    if not body:
        return JsonResponse({'ok': False, 'error': 'Message body is required.'}, status=400)

    try:
        to_list = validate_to_addresses(to_raw)
        cc_list = validate_cc_addresses(cc_raw)
    except ValueError as exc:
        return JsonResponse({'ok': False, 'error': str(exc)}, status=400)

    company = CompanySettings.get_settings()
    pdf, pdf_err = render_po_pdf_bytes(request, po)
    if not pdf:
        return JsonResponse(
            {'ok': False, 'error': pdf_err or 'Could not generate PDF attachment.'},
            status=400,
        )

    from django.core.mail import EmailMessage

    connection = get_smtp_connection_or_default(company)
    from_email = company_outgoing_from_email(company)

    msg = EmailMessage(
        subject=subject,
        body=body,
        from_email=from_email,
        to=to_list,
        cc=cc_list,
        connection=connection,
    )
    msg.content_subtype = 'plain'
    safe_name = ''.join(c for c in po.po_number if c.isalnum() or c in ('-', '_')) or str(po.pk)
    msg.attach(f'PO_{safe_name}.pdf', pdf, 'application/pdf')

    try:
        msg.send(fail_silently=False)
    except Exception as exc:
        return JsonResponse({'ok': False, 'error': f'Could not send email: {exc}'}, status=502)

    return JsonResponse({'ok': True, 'message': 'Email sent.'})


@login_required
def po_delete(request, pk):
    po = get_object_or_404(PurchaseOrder, pk=pk)
    if request.user.is_superuser or PermissionChecker.has_permission(request.user, 'purchase', 'delete'):
        po.is_active = False
        po.save()
        messages.success(request, f'PO {po.po_number} deleted.')
    else:
        messages.error(request, 'Permission denied.')
    return redirect('purchase:po_list')


# ============ VENDOR BILL VIEWS ============

class VendorBillListView(PermissionRequiredMixin, ListView):
    model = VendorBill
    template_name = 'purchase/bill_list.html'
    context_object_name = 'bills'
    module_name = 'purchase'
    permission_type = 'view'
    paginate_by = 25
    
    def get_queryset(self):
        queryset = VendorBill.objects.filter(is_active=True).select_related('vendor', 'project')
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(bill_number__icontains=search) |
                Q(vendor__name__icontains=search)
            )
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Vendor Bills'
        context['status_choices'] = VendorBill.STATUS_CHOICES
        context['can_create'] = self.request.user.is_superuser or PermissionChecker.has_permission(self.request.user, 'purchase', 'create')
        context['can_edit'] = self.request.user.is_superuser or PermissionChecker.has_permission(self.request.user, 'purchase', 'edit')
        context['can_delete'] = self.request.user.is_superuser or PermissionChecker.has_permission(self.request.user, 'purchase', 'delete')
        context['today'] = date.today().isoformat()
        
        # Summary
        bills = self.get_queryset()
        context['total_billed'] = bills.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        context['total_paid'] = bills.aggregate(Sum('paid_amount'))['paid_amount__sum'] or 0
        context['total_outstanding'] = context['total_billed'] - context['total_paid']
        return context


class VendorBillCreateView(CreatePermissionMixin, CreateView):
    model = VendorBill
    form_class = VendorBillForm
    template_name = 'purchase/bill_form.html'
    success_url = reverse_lazy('purchase:bill_list')
    module_name = 'purchase'

    def get_initial(self):
        initial = super().get_initial()
        po_id = self.request.GET.get('po')
        if po_id:
            initial['purchase_order'] = po_id
            initial['goods_received'] = True
        return initial
    
    def get_context_data(self, **kwargs):
        from apps.finance.models import TaxCode
        context = super().get_context_data(**kwargs)
        context['title'] = 'Create Vendor Bill'
        context['today'] = date.today().isoformat()
        context['preselect_po'] = self.request.GET.get('po')
        context['bill_received_mode'] = self.request.GET.get('from_received', '1')
        # Tax Codes for VAT selection (SAP/Oracle Standard)
        context['tax_codes'] = TaxCode.objects.filter(is_active=True).order_by('code')
        context['default_tax_code'] = TaxCode.objects.filter(is_active=True, is_default=True).first()
        if 'items_formset' not in kwargs:
            if self.request.POST:
                context['items_formset'] = VendorBillItemFormSet(self.request.POST)
            else:
                context['items_formset'] = VendorBillItemFormSet()
        else:
            context['items_formset'] = kwargs['items_formset']
        return context
    
    def post(self, request, *args, **kwargs):
        self.object = None
        form = self.get_form()
        items_formset = VendorBillItemFormSet(request.POST)
        
        if form.is_valid() and items_formset.is_valid():
            return self.form_valid(form, items_formset)
        else:
            return self.form_invalid(form, items_formset)
    
    def form_valid(self, form, items_formset):
        from .po_billing import bill_formset_lines_for_validation, validate_vendor_bill_po_lines

        bill = form.save(commit=False)
        line_rows = bill_formset_lines_for_validation(items_formset)
        po_errors = validate_vendor_bill_po_lines(bill, line_rows)
        if po_errors:
            for err in po_errors:
                form.add_error(None, err)
            return self.form_invalid(form, items_formset)

        self.object = form.save()
        items_formset.instance = self.object
        items_formset.save()
        _save_vendor_bill_attachments(self.request, self.object)
        self.object.calculate_totals()
        messages.success(self.request, f'Vendor Bill {self.object.bill_number} created.')
        return redirect(self.success_url)
    
    def form_invalid(self, form, items_formset):
        return self.render_to_response(
            self.get_context_data(form=form, items_formset=items_formset)
        )


class VendorBillUpdateView(UpdatePermissionMixin, UpdateView):
    """Edit a vendor bill - only draft bills can be edited."""
    model = VendorBill
    form_class = VendorBillForm
    template_name = 'purchase/bill_form.html'
    module_name = 'purchase'
    
    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        # Block editing posted bills
        if obj.status != 'draft':
            messages.error(self.request, 'Posted bills cannot be edited. Only draft bills are editable.')
            return None
        return obj
    
    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object is None:
            return redirect('purchase:bill_list')
        return super().get(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        from apps.finance.models import TaxCode
        context = super().get_context_data(**kwargs)
        context['title'] = f'Edit Bill: {self.object.bill_number}'
        context['today'] = date.today().isoformat()
        context['preselect_po'] = None
        context['bill_received_mode'] = '1'
        # Tax Codes for VAT selection (SAP/Oracle Standard)
        context['tax_codes'] = TaxCode.objects.filter(is_active=True).order_by('code')
        context['default_tax_code'] = TaxCode.objects.filter(is_active=True, is_default=True).first()
        if 'items_formset' not in kwargs:
            if self.request.POST:
                context['items_formset'] = VendorBillItemFormSet(self.request.POST, instance=self.object)
            else:
                context['items_formset'] = VendorBillItemFormSet(instance=self.object)
        else:
            context['items_formset'] = kwargs['items_formset']
        return context
    
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object is None:
            return redirect('purchase:bill_list')
        form = self.get_form()
        items_formset = VendorBillItemFormSet(request.POST, instance=self.object)
        
        if form.is_valid() and items_formset.is_valid():
            return self.form_valid(form, items_formset)
        else:
            return self.form_invalid(form, items_formset)
    
    def form_valid(self, form, items_formset):
        from .po_billing import bill_formset_lines_for_validation, validate_vendor_bill_po_lines

        bill = form.save(commit=False)
        line_rows = bill_formset_lines_for_validation(items_formset)
        po_errors = validate_vendor_bill_po_lines(
            bill, line_rows, exclude_bill_id=self.object.pk
        )
        if po_errors:
            for err in po_errors:
                form.add_error(None, err)
            return self.form_invalid(form, items_formset)

        self.object = form.save()
        items_formset.instance = self.object
        items_formset.save()
        _save_vendor_bill_attachments(self.request, self.object)
        self.object.calculate_totals()
        messages.success(self.request, f'Vendor Bill {self.object.bill_number} updated.')
        return redirect('purchase:bill_detail', pk=self.object.pk)
    
    def form_invalid(self, form, items_formset):
        return self.render_to_response(
            self.get_context_data(form=form, items_formset=items_formset)
        )


class VendorBillDetailView(PermissionRequiredMixin, DetailView):
    model = VendorBill
    template_name = 'purchase/bill_detail.html'
    context_object_name = 'bill'
    module_name = 'purchase'
    permission_type = 'view'

    def get_queryset(self):
        return (
            VendorBill.objects.filter(is_active=True)
            .select_related('vendor', 'journal_entry', 'project', 'purchase_order')
            .prefetch_related('items', 'attachments')
        )

    def get_context_data(self, **kwargs):
        from apps.core.audit import get_entity_audit_history
        
        context = super().get_context_data(**kwargs)
        context['title'] = f'Bill: {self.object.bill_number}'
        has_permission = self.request.user.is_superuser or PermissionChecker.has_permission(self.request.user, 'purchase', 'edit')
        # Only allow editing draft bills
        context['can_edit'] = has_permission and self.object.status == 'draft'
        # Allow posting draft bills
        context['can_post'] = has_permission and self.object.status == 'draft' and self.object.total_amount > 0
        context['can_create_debit_note'] = (
            has_permission
            and self.object.status in DebitNote.DEBITABLE_BILL_STATUSES
        )
        context['debit_notes'] = self.object.debit_notes.filter(is_active=True).order_by('-created_at')
        context['debit_notes_total'] = DebitNote.posted_total_for_bill(self.object)
        context['audit_history'] = get_entity_audit_history('Bill', self.object.pk)
        
        return context


@login_required
def bill_delete(request, pk):
    bill = get_object_or_404(VendorBill, pk=pk)
    if request.user.is_superuser or PermissionChecker.has_permission(request.user, 'purchase', 'delete'):
        bill.is_active = False
        bill.save()
        messages.success(request, f'Bill {bill.bill_number} deleted.')
    else:
        messages.error(request, 'Permission denied.')
    return redirect('purchase:bill_list')


@login_required
def bill_post(request, pk):
    """
    Post vendor bill to accounting - creates journal entry.
    Debit Expense, Debit VAT Recoverable, Credit AP
    """
    from apps.core.audit import audit_bill_post
    
    bill = get_object_or_404(VendorBill, pk=pk)
    
    if not (request.user.is_superuser or PermissionChecker.has_permission(request.user, 'purchase', 'edit')):
        messages.error(request, 'Permission denied.')
        return redirect('purchase:bill_list')
    
    if bill.status != 'draft':
        messages.error(request, 'Only draft bills can be posted to accounting.')
        return redirect('purchase:bill_detail', pk=pk)
    
    try:
        journal = bill.post_to_accounting(user=request.user)
        # Audit log with IP address
        audit_bill_post(bill, request.user, request=request)
        messages.success(request, f'Bill {bill.bill_number} posted to accounting. Journal: {journal.entry_number}')
    except ValidationError as e:
        messages.error(request, str(e))
    except Exception as e:
        messages.error(request, f'Error posting bill: {e}')
    
    return redirect('purchase:bill_detail', pk=pk)


# ============ EXPENSE CLAIM VIEWS ============

class ExpenseClaimListView(PermissionRequiredMixin, ListView):
    """
    List all expense claims.
    Moved from Finance module to Purchase module.
    """
    model = ExpenseClaim
    template_name = 'purchase/expenseclaim_list.html'
    context_object_name = 'claims'
    module_name = 'purchase'
    permission_type = 'view'
    paginate_by = 25
    
    def get_queryset(self):
        queryset = ExpenseClaim.objects.filter(is_active=True).select_related('employee')
        
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(claim_number__icontains=search) |
                Q(employee__first_name__icontains=search) |
                Q(employee__last_name__icontains=search)
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Expense Claims'
        context['status_choices'] = ExpenseClaim.STATUS_CHOICES
        context['can_create'] = self.request.user.is_superuser or PermissionChecker.has_permission(self.request.user, 'purchase', 'create')
        context['can_edit'] = self.request.user.is_superuser or PermissionChecker.has_permission(self.request.user, 'purchase', 'edit')
        context['can_approve'] = self.request.user.is_superuser or PermissionChecker.has_permission(self.request.user, 'purchase', 'approve')
        context['today'] = date.today().isoformat()
        
        # Metrics
        all_claims = ExpenseClaim.objects.filter(is_active=True)
        context['total_claims'] = all_claims.count()
        context['pending_claims'] = all_claims.filter(status='submitted').count()
        context['approved_unpaid'] = all_claims.filter(status='approved').count()
        context['total_amount'] = all_claims.aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
        
        return context


class ExpenseClaimCreateView(CreatePermissionMixin, CreateView):
    """Create a new expense claim."""
    model = ExpenseClaim
    form_class = ExpenseClaimForm
    template_name = 'purchase/expenseclaim_form.html'
    success_url = reverse_lazy('purchase:expenseclaim_list')
    module_name = 'purchase'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Create Expense Claim'
        context['today'] = date.today().isoformat()
        if self.request.POST:
            context['items_formset'] = ExpenseClaimItemFormSet(self.request.POST, self.request.FILES)
        else:
            context['items_formset'] = ExpenseClaimItemFormSet()
        return context
    
    def form_valid(self, form):
        context = self.get_context_data()
        items_formset = context['items_formset']
        
        if items_formset.is_valid():
            form.instance.employee = self.request.user
            self.object = form.save()
            items_formset.instance = self.object
            items_formset.save()
            self.object.calculate_totals()
            messages.success(self.request, f'Expense Claim {self.object.claim_number} created.')
            return redirect(self.success_url)
        else:
            return self.render_to_response(context)


class ExpenseClaimDetailView(PermissionRequiredMixin, DetailView):
    """View expense claim details."""
    model = ExpenseClaim
    template_name = 'purchase/expenseclaim_detail.html'
    context_object_name = 'claim'
    module_name = 'purchase'
    permission_type = 'view'
    
    def get_context_data(self, **kwargs):
        from apps.core.audit import get_entity_audit_history
        
        context = super().get_context_data(**kwargs)
        context['title'] = f'Expense Claim: {self.object.claim_number}'
        
        # Permissions
        has_permission = self.request.user.is_superuser or PermissionChecker.has_permission(self.request.user, 'purchase', 'edit')
        can_approve = self.request.user.is_superuser or PermissionChecker.has_permission(self.request.user, 'purchase', 'approve')
        
        context['can_submit'] = has_permission and self.object.status == 'draft'
        context['can_approve'] = can_approve and self.object.status == 'submitted'
        context['can_reject'] = can_approve and self.object.status == 'submitted'
        context['can_pay'] = has_permission and self.object.status == 'approved'
        
        # Payment form for approved claims
        if self.object.status == 'approved':
            context['payment_form'] = ExpenseClaimPaymentForm(initial={'payment_date': date.today()})
        
        # Audit History
        context['audit_history'] = get_entity_audit_history('ExpenseClaim', self.object.pk)
        
        return context


@login_required
def expenseclaim_submit(request, pk):
    """Submit expense claim for approval."""
    claim = get_object_or_404(ExpenseClaim, pk=pk)
    
    if claim.status != 'draft':
        messages.error(request, 'Only draft claims can be submitted.')
        return redirect('purchase:expenseclaim_detail', pk=pk)
    
    if claim.items.count() == 0:
        messages.error(request, 'Cannot submit claim without any expense items.')
        return redirect('purchase:expenseclaim_detail', pk=pk)
    
    claim.status = 'submitted'
    claim.save()
    messages.success(request, f'Expense Claim {claim.claim_number} submitted for approval.')
    return redirect('purchase:expenseclaim_detail', pk=pk)


@login_required
def expenseclaim_approve(request, pk):
    """
    Approve an expense claim and post to accounting.
    Creates journal entry: Dr Expense, Dr VAT Recoverable, Cr Employee Payable
    """
    from apps.core.audit import audit_expense_approve
    
    claim = get_object_or_404(ExpenseClaim, pk=pk)
    
    if not (request.user.is_superuser or PermissionChecker.has_permission(request.user, 'purchase', 'approve')):
        messages.error(request, 'Permission denied.')
        return redirect('purchase:expenseclaim_detail', pk=pk)
    
    if claim.status != 'submitted':
        messages.error(request, 'Only submitted claims can be approved.')
        return redirect('purchase:expenseclaim_detail', pk=pk)
    
    claim.status = 'approved'
    claim.approved_by = request.user
    claim.approved_date = timezone.now()
    claim.save()
    
    # Post to accounting
    try:
        journal = claim.post_approval_journal(user=request.user)
        # Audit log with IP address
        audit_expense_approve(claim, request.user, request=request)
        messages.success(request, f'Expense Claim {claim.claim_number} approved and posted to accounting. Journal: {journal.entry_number}')
    except ValidationError as e:
        messages.warning(request, f'Claim approved but journal entry failed: {str(e)}')
    except Exception as e:
        messages.warning(request, f'Claim approved but journal entry failed: {str(e)}')
    
    return redirect('purchase:expenseclaim_detail', pk=pk)


@login_required
def expenseclaim_reject(request, pk):
    """Reject an expense claim."""
    claim = get_object_or_404(ExpenseClaim, pk=pk)
    
    if not (request.user.is_superuser or PermissionChecker.has_permission(request.user, 'purchase', 'approve')):
        messages.error(request, 'Permission denied.')
        return redirect('purchase:expenseclaim_detail', pk=pk)
    
    if claim.status != 'submitted':
        messages.error(request, 'Only submitted claims can be rejected.')
        return redirect('purchase:expenseclaim_detail', pk=pk)
    
    reason = request.POST.get('rejection_reason', '')
    claim.status = 'rejected'
    claim.rejection_reason = reason
    claim.save()
    
    messages.success(request, f'Expense Claim {claim.claim_number} rejected.')
    return redirect('purchase:expenseclaim_detail', pk=pk)


@login_required
def expenseclaim_pay(request, pk):
    """
    Pay an approved expense claim.
    Creates journal entry: Dr Employee Payable, Cr Bank Account
    """
    claim = get_object_or_404(ExpenseClaim, pk=pk)
    
    if not (request.user.is_superuser or PermissionChecker.has_permission(request.user, 'purchase', 'edit')):
        messages.error(request, 'Permission denied.')
        return redirect('purchase:expenseclaim_detail', pk=pk)
    
    if claim.status != 'approved':
        messages.error(request, 'Only approved claims can be paid.')
        return redirect('purchase:expenseclaim_detail', pk=pk)
    
    if request.method == 'POST':
        form = ExpenseClaimPaymentForm(request.POST)
        if form.is_valid():
            try:
                journal = claim.post_payment_journal(
                    bank_account=form.cleaned_data['bank_account'],
                    payment_date=form.cleaned_data['payment_date'],
                    reference=form.cleaned_data['payment_reference'],
                    user=request.user
                )
                messages.success(request, f'Expense Claim {claim.claim_number} paid. Journal: {journal.entry_number}')
            except ValidationError as e:
                messages.error(request, str(e))
            except Exception as e:
                messages.error(request, f'Error processing payment: {str(e)}')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    
    return redirect('purchase:expenseclaim_detail', pk=pk)


# ============ RECURRING EXPENSE VIEWS ============

class RecurringExpenseListView(PermissionRequiredMixin, ListView):
    """List all recurring expenses."""
    model = RecurringExpense
    template_name = 'purchase/recurringexpense_list.html'
    context_object_name = 'recurring_expenses'
    module_name = 'purchase'
    permission_type = 'view'
    paginate_by = 25
    
    def get_queryset(self):
        queryset = RecurringExpense.objects.filter(is_active=True).select_related(
            'vendor', 'expense_account', 'bank_account'
        )
        
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(vendor__name__icontains=search)
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Recurring Expenses'
        context['status_choices'] = RecurringExpense.STATUS_CHOICES
        context['can_create'] = self.request.user.is_superuser or PermissionChecker.has_permission(self.request.user, 'purchase', 'create')
        context['can_edit'] = self.request.user.is_superuser or PermissionChecker.has_permission(self.request.user, 'purchase', 'edit')
        context['can_delete'] = self.request.user.is_superuser or PermissionChecker.has_permission(self.request.user, 'purchase', 'delete')
        context['today'] = date.today()
        
        # Metrics
        all_recurring = RecurringExpense.objects.filter(is_active=True)
        context['total_recurring'] = all_recurring.count()
        context['active_recurring'] = all_recurring.filter(status='active').count()
        context['monthly_total'] = all_recurring.filter(
            status='active', frequency='monthly'
        ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
        
        # Due this month
        today = date.today()
        context['due_this_month'] = all_recurring.filter(
            status='active',
            next_run_date__year=today.year,
            next_run_date__month=today.month
        ).count()
        
        return context


class RecurringExpenseCreateView(CreatePermissionMixin, CreateView):
    """Create a new recurring expense."""
    model = RecurringExpense
    form_class = RecurringExpenseForm
    template_name = 'purchase/recurringexpense_form.html'
    success_url = reverse_lazy('purchase:recurringexpense_list')
    module_name = 'purchase'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Create Recurring Expense'
        context['today'] = date.today().isoformat()
        return context
    
    def form_valid(self, form):
        self.object = form.save()
        messages.success(self.request, f'Recurring Expense "{self.object.name}" created.')
        return redirect(self.success_url)


class RecurringExpenseUpdateView(UpdatePermissionMixin, UpdateView):
    """Edit a recurring expense."""
    model = RecurringExpense
    form_class = RecurringExpenseForm
    template_name = 'purchase/recurringexpense_form.html'
    success_url = reverse_lazy('purchase:recurringexpense_list')
    module_name = 'purchase'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Edit: {self.object.name}'
        context['today'] = date.today().isoformat()
        return context
    
    def form_valid(self, form):
        self.object = form.save()
        messages.success(self.request, f'Recurring Expense "{self.object.name}" updated.')
        return redirect(self.success_url)


class RecurringExpenseDetailView(PermissionRequiredMixin, DetailView):
    """View recurring expense details and execution history."""
    model = RecurringExpense
    template_name = 'purchase/recurringexpense_detail.html'
    context_object_name = 'recurring_expense'
    module_name = 'purchase'
    permission_type = 'view'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Recurring Expense: {self.object.name}'
        context['logs'] = self.object.logs.all()[:20]  # Last 20 executions
        
        has_permission = self.request.user.is_superuser or PermissionChecker.has_permission(self.request.user, 'purchase', 'edit')
        context['can_edit'] = has_permission
        context['can_execute'] = has_permission and self.object.status == 'active'
        context['can_pause'] = has_permission and self.object.status == 'active'
        context['can_resume'] = has_permission and self.object.status == 'paused'
        
        return context


@login_required
def recurringexpense_delete(request, pk):
    """Soft delete a recurring expense."""
    expense = get_object_or_404(RecurringExpense, pk=pk)
    if request.user.is_superuser or PermissionChecker.has_permission(request.user, 'purchase', 'delete'):
        expense.is_active = False
        expense.save()
        messages.success(request, f'Recurring Expense "{expense.name}" deleted.')
    else:
        messages.error(request, 'Permission denied.')
    return redirect('purchase:recurringexpense_list')


@login_required
def recurringexpense_execute(request, pk):
    """Manually execute a recurring expense (generate expense and journal entry)."""
    expense = get_object_or_404(RecurringExpense, pk=pk)
    
    if not (request.user.is_superuser or PermissionChecker.has_permission(request.user, 'purchase', 'edit')):
        messages.error(request, 'Permission denied.')
        return redirect('purchase:recurringexpense_detail', pk=pk)
    
    if expense.status != 'active':
        messages.error(request, 'Only active recurring expenses can be executed.')
        return redirect('purchase:recurringexpense_detail', pk=pk)
    
    try:
        log = expense.execute(user=request.user)
        if log:
            if log.status == 'success':
                messages.success(request, f'Recurring expense executed successfully. Journal: {log.journal_entry.entry_number if log.journal_entry else "N/A"}')
            else:
                messages.warning(request, f'Execution failed: {log.error_message}')
        else:
            messages.info(request, 'Expense not due for execution or already completed.')
    except Exception as e:
        messages.error(request, f'Error executing recurring expense: {str(e)}')
    
    return redirect('purchase:recurringexpense_detail', pk=pk)


@login_required
def recurringexpense_pause(request, pk):
    """Pause a recurring expense."""
    expense = get_object_or_404(RecurringExpense, pk=pk)
    
    if not (request.user.is_superuser or PermissionChecker.has_permission(request.user, 'purchase', 'edit')):
        messages.error(request, 'Permission denied.')
        return redirect('purchase:recurringexpense_detail', pk=pk)
    
    if expense.status != 'active':
        messages.error(request, 'Only active recurring expenses can be paused.')
        return redirect('purchase:recurringexpense_detail', pk=pk)
    
    expense.status = 'paused'
    expense.save()
    messages.success(request, f'Recurring Expense "{expense.name}" paused.')
    return redirect('purchase:recurringexpense_detail', pk=pk)


@login_required
def recurringexpense_resume(request, pk):
    """Resume a paused recurring expense."""
    expense = get_object_or_404(RecurringExpense, pk=pk)
    
    if not (request.user.is_superuser or PermissionChecker.has_permission(request.user, 'purchase', 'edit')):
        messages.error(request, 'Permission denied.')
        return redirect('purchase:recurringexpense_detail', pk=pk)
    
    if expense.status != 'paused':
        messages.error(request, 'Only paused recurring expenses can be resumed.')
        return redirect('purchase:recurringexpense_detail', pk=pk)
    
    expense.status = 'active'
    expense.save()
    messages.success(request, f'Recurring Expense "{expense.name}" resumed.')
    return redirect('purchase:recurringexpense_detail', pk=pk)



# ============ PAYMENT VOUCHER FOR VENDOR BILL ============

@login_required
def bill_make_payment(request, pk):
    """
    Record payment made for a vendor bill.
    SAP/Oracle Standard: Payment creates clearing entry for AP.

    Dr Accounts Payable
    Cr Bank
    """
    from apps.finance.models import BankAccount
    from .vendor_bill_payment import (
        record_vendor_bill_payment,
        resolve_bank_account,
        parse_payment_date,
    )

    bill = get_object_or_404(VendorBill, pk=pk)

    if not (request.user.is_superuser or PermissionChecker.has_permission(request.user, 'purchase', 'edit')):
        messages.error(request, 'Permission denied.')
        return redirect('purchase:bill_detail', pk=pk)

    if bill.status == 'draft':
        messages.error(request, 'Bill must be posted to accounting before making payment.')
        return redirect('purchase:bill_detail', pk=pk)

    if bill.balance <= 0:
        messages.error(request, 'Bill is already fully paid.')
        return redirect('purchase:bill_detail', pk=pk)

    if request.method == 'POST':
        payment_method = request.POST.get('payment_method', 'bank')
        bank_account_id = request.POST.get('bank_account')
        reference = request.POST.get('reference', '')

        try:
            amount = Decimal(request.POST.get('amount'))
            if amount <= 0:
                raise ValueError('Amount must be positive')
            if amount > bill.balance:
                messages.warning(request, f'Amount exceeds balance. Adjusted to {bill.balance}')
                amount = bill.balance
        except (ValueError, InvalidOperation) as exc:
            messages.error(request, f'Invalid amount: {exc}')
            return redirect('purchase:bill_detail', pk=pk)

        try:
            bank_account = resolve_bank_account(payment_method, bank_account_id)
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect('purchase:bill_detail', pk=pk)

        payment_date = parse_payment_date(request.POST.get('payment_date'))

        payment, error = record_vendor_bill_payment(
            bill,
            amount,
            payment_method,
            bank_account,
            payment_date,
            reference,
            request.user,
        )
        if error:
            messages.error(request, error)
        else:
            messages.success(
                request,
                f'Payment of AED {payment.amount:,.2f} recorded. Voucher: {payment.payment_number}',
            )

        return redirect('purchase:bill_detail', pk=pk)

    bank_accounts = BankAccount.objects.filter(is_active=True)
    context = {
        'title': f'Make Payment - {bill.bill_number}',
        'bill': bill,
        'bank_accounts': bank_accounts,
        'today': date.today().strftime('%Y-%m-%d'),
    }
    return render(request, 'purchase/bill_make_payment.html', context)


@login_required
@require_POST
def bill_bulk_pay_prepare(request):
    """Post draft bills and return payment summary for the bulk payment modal."""
    from apps.core.audit import audit_bill_post
    from apps.finance.models import BankAccount

    if not (request.user.is_superuser or PermissionChecker.has_permission(request.user, 'purchase', 'edit')):
        return JsonResponse({'error': 'Permission denied.'}, status=403)

    bill_ids = request.POST.getlist('bill_ids')
    if not bill_ids:
        return JsonResponse({'error': 'Select at least one bill.'}, status=400)

    bills = list(
        VendorBill.objects.filter(pk__in=bill_ids, is_active=True).select_related('vendor')
    )
    if not bills:
        return JsonResponse({'error': 'No valid bills selected.'}, status=400)

    posting_errors = []
    for bill in bills:
        if bill.status != 'draft':
            continue
        try:
            bill.post_to_accounting(user=request.user)
            try:
                audit_bill_post(bill, request.user, request=request)
            except Exception as audit_exc:
                posting_errors.append(f'{bill.bill_number}: posted but audit log failed — {audit_exc}')
        except (ValidationError, Exception) as exc:
            posting_errors.append(f'{bill.bill_number}: {exc}')

    bills = list(
        VendorBill.objects.filter(pk__in=bill_ids, is_active=True).select_related('vendor')
    )

    payable_bills = []
    total_balance = Decimal('0.00')
    for bill in bills:
        bill.refresh_from_db()
        if bill.status == 'draft' or bill.balance <= 0:
            continue
        payable_bills.append({
            'id': bill.pk,
            'bill_number': bill.bill_number,
            'vendor': bill.vendor.name,
            'balance': str(bill.balance),
        })
        total_balance += bill.balance

    if not payable_bills:
        error = 'No bills available for payment.'
        if posting_errors:
            error = posting_errors[0]
        return JsonResponse({'error': error, 'posting_errors': posting_errors}, status=400)

    bank_accounts = [
        {
            'id': bank.pk,
            'name': str(bank),
        }
        for bank in BankAccount.objects.filter(is_active=True)
    ]

    return JsonResponse({
        'bills': payable_bills,
        'total_balance': str(total_balance),
        'bank_accounts': bank_accounts,
        'today': date.today().strftime('%Y-%m-%d'),
        'posting_errors': posting_errors,
    })


@login_required
@require_POST
def bill_bulk_pay(request):
    """Record payments for multiple vendor bills from the list bulk payment modal."""
    from .vendor_bill_payment import (
        record_vendor_bill_payment,
        resolve_bank_account,
        parse_payment_date,
    )

    if not (request.user.is_superuser or PermissionChecker.has_permission(request.user, 'purchase', 'edit')):
        messages.error(request, 'Permission denied.')
        return redirect('purchase:bill_list')

    bill_ids = request.POST.getlist('bill_ids')
    if not bill_ids:
        messages.error(request, 'Select at least one bill.')
        return redirect('purchase:bill_list')

    payment_method = request.POST.get('payment_method', 'bank')
    reference = request.POST.get('reference', '')

    try:
        bank_account = resolve_bank_account(payment_method, request.POST.get('bank_account'))
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect('purchase:bill_list')

    payment_date = parse_payment_date(request.POST.get('payment_date'))

    try:
        total_payment_amount = Decimal(request.POST.get('amount', '0'))
        if total_payment_amount <= 0:
            raise ValueError('Amount must be positive')
    except (ValueError, InvalidOperation) as exc:
        messages.error(request, f'Invalid amount: {exc}')
        return redirect('purchase:bill_list')

    bills = list(
        VendorBill.objects.filter(pk__in=bill_ids, is_active=True)
        .select_related('vendor')
        .order_by('bill_date', 'pk')
    )

    from apps.core.audit import audit_bill_post

    success_count = 0
    errors = []

    for bill in bills:
        if bill.status != 'draft':
            continue
        try:
            bill.post_to_accounting(user=request.user)
            audit_bill_post(bill, request.user, request=request)
        except (ValidationError, Exception) as exc:
            errors.append(f'{bill.bill_number}: could not post — {exc}')

    bills = list(
        VendorBill.objects.filter(pk__in=bill_ids, is_active=True)
        .select_related('vendor')
        .order_by('bill_date', 'pk')
    )

    remaining = total_payment_amount

    for bill in bills:
        if bill.status == 'draft' or bill.balance <= 0:
            continue
        if remaining <= 0:
            break

        pay_amount = min(bill.balance, remaining)
        payment, error = record_vendor_bill_payment(
            bill,
            pay_amount,
            payment_method,
            bank_account,
            payment_date,
            reference,
            request.user,
        )
        if error:
            errors.append(f'{bill.bill_number}: {error}')
        else:
            success_count += 1
            remaining -= pay_amount

    if success_count:
        messages.success(request, f'Payment recorded for {success_count} bill(s).')
    for err in errors:
        messages.error(request, err)
    if not success_count and not errors:
        messages.warning(request, 'No payments were recorded.')

    return redirect('purchase:bill_list')
