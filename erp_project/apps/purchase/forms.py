"""
Purchase Forms - Including Expense Claims and Recurring Expenses

VAT LOGIC (Tax Code Driven - SAP/Oracle Standard):
- VAT is ALWAYS derived from a TaxCode
- No Tax Code = No VAT (Out of Scope)
- VAT rate is read-only, computed from Tax Code
"""
from decimal import Decimal

from django import forms
from django.db.models import Q
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory
from .models import (
    Vendor, PurchaseRequest, PurchaseRequestItem,
    PurchaseOrder, PurchaseOrderItem, VendorBill, VendorBillItem,
    ExpenseClaim, ExpenseClaimItem, RecurringExpense,
    DebitNote, DebitNoteLine,
)
from apps.finance.models import TaxCode
from apps.projects.models import Project


class VendorForm(forms.ModelForm):
    """Form for creating/editing vendors."""
    
    class Meta:
        model = Vendor
        fields = [
            'is_active', 'name', 'contact_person', 'email', 'phone', 'address',
            'city', 'country', 'trn', 'website', 'trn_document', 'trade_license_document',
            'payment_terms', 'credit_limit', 'status', 'notes',
        ]
        widgets = {
            'address': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'trn_document': forms.FileInput(
                attrs={
                    'class': 'form-control form-control-sm',
                    'accept': '.pdf,.jpg,.jpeg,.png,.webp,.heic',
                }
            ),
            'trade_license_document': forms.FileInput(
                attrs={
                    'class': 'form-control form-control-sm',
                    'accept': '.pdf,.jpg,.jpeg,.png,.webp,.heic',
                }
            ),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['is_active'].label = 'Is active'
        self.fields['is_active'].widget = forms.CheckboxInput(attrs={'class': 'form-check-input'})
        self.fields['trn_document'].required = False
        self.fields['trade_license_document'].required = False
        self.fields['trn'].label = 'Tax Registration Number (TRN)'
        self.fields['website'].required = False
        self.fields['payment_terms'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Net 30',
        })
        self.fields['credit_limit'].widget = forms.NumberInput(
            attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}
        )
        self.fields['city'].widget.attrs.update({'class': 'form-control', 'placeholder': 'City'})
        self.fields['country'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Country'})
        for field_name, field in self.fields.items():
            if field_name in ('address', 'notes', 'payment_terms', 'credit_limit', 'city', 'country', 'is_active'):
                continue
            elif field_name in ('trn_document', 'trade_license_document'):
                continue
            elif field_name == 'status':
                field.widget.attrs['class'] = 'form-select'
            else:
                field.widget.attrs['class'] = 'form-control'
            if field_name == 'trn':
                field.widget.attrs['placeholder'] = 'VAT / TRN number'
            elif field_name == 'website':
                field.widget.attrs['placeholder'] = 'gear-up.ae, www.gear-up.ae, or https://gear-up.ae'
        if not self.is_bound and not self.instance.pk:
            self.fields['is_active'].initial = True
            if 'country' not in self.initial:
                self.initial['country'] = 'United Arab Emirates'

    def clean_website(self):
        from apps.crm.utils import normalize_customer_website

        raw = self.cleaned_data.get('website') or ''
        try:
            return normalize_customer_website(raw)
        except ValidationError:
            raise forms.ValidationError(
                'Enter a valid website (e.g. gear-up.ae, www.gear-up.ae, or https://gear-up.ae).'
            )

    def clean(self):
        cleaned = super().clean()
        if self.is_bound:
            cleaned['is_active'] = 'is_active' in self.data
        if self.data.get('trn_document-clear') in ('on', 'true', '1'):
            cleaned['trn_document'] = False
        if self.data.get('trade_license_document-clear') in ('on', 'true', '1'):
            cleaned['trade_license_document'] = False
        return cleaned


class PurchaseRequestForm(forms.ModelForm):
    """Form for creating/editing purchase requests."""

    edit_exclude = ['service_request']

    class Meta:
        model = PurchaseRequest
        fields = [
            'is_active', 'date', 'required_by_date', 'department', 'priority', 'status',
            'vendor', 'service_request', 'notes',
        ]
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d'),
            'required_by_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d'),
            'department': forms.Select(attrs={'class': 'form-select'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'vendor': forms.Select(attrs={'class': 'form-select select2-pr-vendor'}),
            'service_request': forms.Select(attrs={'class': 'form-select select2-pr-sr'}),
            'notes': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.hr.models import Department

        self.fields['is_active'].label = 'Is active'
        self.fields['is_active'].widget = forms.CheckboxInput(attrs={'class': 'form-check-input'})
        is_edit = self.instance and self.instance.pk
        if is_edit:
            for field_name in self.edit_exclude:
                if field_name in self.fields:
                    del self.fields[field_name]

        self.fields['department'].queryset = Department.objects.filter(is_active=True)
        self.fields['department'].required = False
        self.fields['status'].widget.attrs['class'] = 'form-select'
        self.fields['vendor'].queryset = Vendor.objects.filter(is_active=True).order_by('name')
        self.fields['vendor'].required = False
        self.fields['vendor'].empty_label = '— Select vendor —'

        if not is_edit:
            from apps.service_request.models import ServiceRequest

            self.fields['service_request'].queryset = ServiceRequest.objects.filter(
                status='approved', is_active=True
            ).order_by('-date', '-pk')
            preselect = self.data.get('service_request') if self.data else None
            if not preselect and self.initial.get('service_request'):
                preselect = self.initial.get('service_request')
            if preselect:
                self.fields['service_request'].queryset = (
                    self.fields['service_request'].queryset
                    | ServiceRequest.objects.filter(pk=preselect, is_active=True)
                ).distinct()
            self.fields['service_request'].required = False
            self.fields['service_request'].empty_label = '— Optional —'
            if not self.is_bound:
                self.fields['is_active'].initial = True

        self.fields['required_by_date'].required = False
        self.fields['notes'].required = False
        if self.instance and self.instance.pk and self.instance.status not in ('draft', 'returned'):
            self.fields['status'].disabled = True
            self.fields['status'].help_text = 'Status is changed through approval workflow, not manual edit.'

    def clean(self):
        cleaned = super().clean()
        if self.is_bound:
            cleaned['is_active'] = 'is_active' in self.data
        return cleaned

    def clean_service_request(self):
        val = self.cleaned_data.get('service_request')
        return val or None


class PurchaseRequestItemForm(forms.ModelForm):
    class Meta:
        model = PurchaseRequestItem
        fields = ['inventory_item', 'description', 'quantity', 'unit', 'estimated_price']
        widgets = {
            'description': forms.HiddenInput(attrs={'class': 'item-description-input'}),
            'estimated_price': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'quantity': forms.NumberInput(attrs={'step': '1', 'min': '0'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.inventory.models import Item

        self.fields['inventory_item'].queryset = Item.objects.filter(
            is_active=True, status='active'
        ).order_by('name')
        self.fields['inventory_item'].required = False
        self.fields['inventory_item'].empty_label = '— Select inventory item —'
        self.fields['inventory_item'].widget.attrs['class'] = 'form-select item-inventory-select'
        self.fields['description'].required = False

        self.fields['unit'].widget.attrs['class'] = 'form-select'
        for name, field in self.fields.items():
            if name in ('inventory_item', 'unit', 'description'):
                continue
            if field.widget.attrs.get('class') != 'form-select':
                field.widget.attrs['class'] = 'form-control'

        if not self.instance.pk:
            self.fields['quantity'].initial = Decimal('0')

        self.fields['quantity'].widget.attrs.update(
            {'class': 'form-control item-qty', 'step': '1', 'min': '0'}
        )
        self.fields['estimated_price'].widget.attrs.update(
            {'class': 'form-control item-cost', 'step': '0.01', 'min': '0'}
        )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('DELETE'):
            return cleaned

        inv = cleaned.get('inventory_item')
        desc = (cleaned.get('description') or '').strip()
        qty = cleaned.get('quantity')
        if qty is None:
            qty = Decimal('0')
        price = cleaned.get('estimated_price')
        if price is None:
            price = Decimal('0')

        if inv:
            if qty <= 0:
                raise forms.ValidationError({'quantity': 'Enter a quantity greater than zero.'})
            return cleaned

        if desc and qty > 0:
            return cleaned

        if self.instance.pk and (self.instance.description or '').strip():
            return cleaned

        if qty > 0 or price > 0:
            raise forms.ValidationError(
                {'inventory_item': 'Select an inventory item or enter a service description.'}
            )
        return cleaned


class BasePurchaseRequestItemFormSet(forms.BaseInlineFormSet):
    """Skip unsaved rows with no catalog item selected (matches dynamic Add Item rows)."""

    def _should_delete_form(self, form):
        if super()._should_delete_form(form):
            return True
        if not form.instance.pk and form.cleaned_data:
            desc = (form.cleaned_data.get('description') or '').strip()
            if not form.cleaned_data.get('inventory_item') and not desc:
                return True
        return False


PurchaseRequestItemFormSet = forms.inlineformset_factory(
    PurchaseRequest,
    PurchaseRequestItem,
    form=PurchaseRequestItemForm,
    formset=BasePurchaseRequestItemFormSet,
    extra=1,
    can_delete=True
)


class PurchaseOrderForm(forms.ModelForm):
    """Form for creating/editing purchase orders."""
    
    class Meta:
        model = PurchaseOrder
        fields = [
            'is_active', 'vendor', 'project', 'purchase_request', 'service_request',
            'order_date', 'expected_delivery_date', 'status', 'notes',
        ]
        widgets = {
            'order_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d'),
            'expected_delivery_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d'),
            'notes': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
        }
    
    # Fields to exclude when editing (source is set at creation only)
    edit_exclude = ['purchase_request', 'service_request']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['is_active'].label = 'Is active'
        self.fields['is_active'].widget = forms.CheckboxInput(attrs={'class': 'form-check-input'})
        is_edit = self.instance and self.instance.pk
        
        # When editing, exclude PR/SR - source is set at creation only, avoids validation issues
        if is_edit:
            for f in self.edit_exclude:
                if f in self.fields:
                    del self.fields[f]
        elif not self.is_bound:
            self.fields['is_active'].initial = True
        
        self.fields['vendor'].queryset = Vendor.objects.filter(is_active=True, status='active')
        self.fields['vendor'].widget.attrs['class'] = 'form-select'

        self.fields['project'].queryset = Project.objects.filter(is_active=True).exclude(
            status='cancelled'
        ).order_by('project_code', 'name')
        self.fields['project'].required = False
        self.fields['project'].widget.attrs['class'] = 'form-select'
        self.fields['project'].empty_label = '— None (not charged to a project) —'
        
        if not is_edit:
            # Show approved PRs (create form only)
            approved_prs = PurchaseRequest.objects.filter(is_active=True, status='approved')
            self.fields['purchase_request'].queryset = approved_prs
            self.fields['purchase_request'].widget.attrs['class'] = 'form-select'
            self.fields['purchase_request'].required = False
            self.fields['purchase_request'].empty_label = "— Optional —"
            
            # Show approved SRs (create form only)
            from apps.service_request.models import ServiceRequest
            approved_srs = ServiceRequest.objects.filter(is_active=True, status='approved')
            preselect = self.data.get('service_request') if self.data else None
            if not preselect and self.initial.get('service_request'):
                preselect = self.initial.get('service_request')
            if preselect:
                approved_srs = (
                    approved_srs | ServiceRequest.objects.filter(pk=preselect, is_active=True)
                ).distinct()
            self.fields['service_request'].queryset = approved_srs.order_by('-date', '-pk')
            self.fields['service_request'].widget.attrs['class'] = 'form-select select2-po-sr'
            self.fields['service_request'].required = False
            self.fields['service_request'].empty_label = "— Optional —"

        self.fields['status'].widget.attrs['class'] = 'form-select'
        self.fields['status'].choices = PurchaseOrder.STATUS_CHOICES
        self.fields['expected_delivery_date'].required = False
        self.fields['notes'].required = False
    
    def clean(self):
        cleaned = super().clean()
        if self.is_bound:
            cleaned['is_active'] = 'is_active' in self.data
        return cleaned

    def clean_service_request(self):
        """Ensure empty value is None - From SR is optional."""
        val = self.cleaned_data.get('service_request')
        return val if val else None
    
    def clean_purchase_request(self):
        """Ensure empty value is None - From PR is optional."""
        val = self.cleaned_data.get('purchase_request')
        return val if val else None


class PurchaseOrderItemForm(forms.ModelForm):
    """
    Form for purchase order line items.
    Tax Code determines VAT rate - No Tax Code = 0% VAT (Out of Scope)
    """

    class Meta:
        model = PurchaseOrderItem
        fields = ['inventory_item', 'description', 'quantity', 'unit_price', 'tax_code', 'is_vat_inclusive']
        widgets = {
            'description': forms.TextInput(
                attrs={
                    'class': 'form-control form-control-sm item-description mt-1',
                    'placeholder': 'Line description (optional)',
                    'maxlength': '500',
                }
            ),
            'quantity': forms.NumberInput(attrs={'step': '1', 'min': '0'}),
            'unit_price': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.inventory.models import Item

        self.fields['inventory_item'].queryset = Item.objects.filter(
            is_active=True, status='active'
        ).order_by('name')
        self.fields['inventory_item'].required = False
        self.fields['inventory_item'].empty_label = '— Select inventory item —'
        self.fields['inventory_item'].widget.attrs['class'] = (
            'form-select form-select-sm item-inventory-select'
        )
        self.fields['description'].required = False

        self.fields['tax_code'].queryset = TaxCode.objects.filter(is_active=True)
        self.fields['tax_code'].required = False
        self.fields['tax_code'].empty_label = '-- No Tax (Out of Scope) --'
        self.fields['tax_code'].widget.attrs['class'] = (
            'form-select form-select-sm item-tax-code'
        )

        self.fields['is_vat_inclusive'].widget = forms.HiddenInput()
        self.fields['is_vat_inclusive'].initial = False

        self.fields['quantity'].widget.attrs.update(
            {'class': 'form-control form-control-sm item-qty', 'step': '1', 'min': '0'}
        )
        self.fields['unit_price'].widget.attrs.update(
            {'class': 'form-control form-control-sm item-price', 'step': '0.01', 'min': '0'}
        )

        if not self.instance.pk:
            self.fields['quantity'].initial = Decimal('0')
            self.fields['unit_price'].initial = Decimal('0')
            default_tax_code = TaxCode.objects.filter(is_active=True, is_default=True).first()
            if default_tax_code:
                self.fields['tax_code'].initial = default_tax_code
    
    def clean_quantity(self):
        qty = self.cleaned_data.get('quantity')
        if qty is None:
            return qty
        return qty.quantize(Decimal('1'))

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('DELETE'):
            return cleaned

        inv = cleaned.get('inventory_item')
        desc = (cleaned.get('description') or '').strip()
        qty = cleaned.get('quantity')
        if qty is None:
            qty = Decimal('0')
        price = cleaned.get('unit_price')
        if price is None:
            price = Decimal('0')

        if inv:
            if qty <= 0:
                raise forms.ValidationError({'quantity': 'Enter a quantity greater than zero.'})
            return cleaned

        if self.instance.pk and desc:
            return cleaned

        if qty > 0 or price > 0:
            raise forms.ValidationError(
                {'inventory_item': 'Select an inventory item for each line.'}
            )
        return cleaned


class BasePurchaseOrderItemFormSet(forms.BaseInlineFormSet):
    """Formset that skips empty extra rows (allows status-only edits)."""
    
    def _should_delete_form(self, form):
        if super()._should_delete_form(form):
            return True
        if not form.instance.pk and form.cleaned_data:
            if not form.cleaned_data.get('inventory_item'):
                return True
        return False


PurchaseOrderItemFormSet = forms.inlineformset_factory(
    PurchaseOrder,
    PurchaseOrderItem,
    form=PurchaseOrderItemForm,
    extra=1,
    can_delete=True,
    formset=BasePurchaseOrderItemFormSet
)


class VendorBillForm(forms.ModelForm):
    """Form for creating/editing vendor bills."""

    class Meta:
        model = VendorBill
        fields = [
            'is_active', 'vendor', 'project', 'purchase_order', 'goods_received',
            'vendor_invoice_number', 'bill_date', 'due_date', 'status', 'notes',
            'discount_type', 'discount_value', 'round_off',
        ]
        widgets = {
            'bill_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d'),
            'due_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d'),
            'notes': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'goods_received': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'discount_type': forms.Select(attrs={'class': 'form-select', 'id': 'id_discount_type'}),
            'discount_value': forms.NumberInput(
                attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'id': 'id_discount_value'},
            ),
            'round_off': forms.NumberInput(
                attrs={'class': 'form-control', 'step': '0.01', 'id': 'id_round_off'},
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['is_active'].label = 'Is active'
        self.fields['is_active'].widget = forms.CheckboxInput(attrs={'class': 'form-check-input'})
        self.fields['vendor'].queryset = Vendor.objects.filter(is_active=True)
        self.fields['vendor'].widget.attrs['class'] = 'form-select'
        self.fields['project'].queryset = Project.objects.filter(is_active=True).exclude(
            status='cancelled'
        ).order_by('name')
        self.fields['project'].required = False
        self.fields['project'].widget.attrs['class'] = 'form-select'
        self.fields['project'].empty_label = '— None (not charged to a project) —'
        self.fields['purchase_order'].queryset = PurchaseOrder.objects.filter(is_active=True)
        self.fields['purchase_order'].widget.attrs['class'] = 'form-select'
        self.fields['purchase_order'].required = False
        self.fields['status'].widget.attrs['class'] = 'form-select'
        self.fields['vendor_invoice_number'].widget.attrs['class'] = 'form-control'
        self.fields['vendor_invoice_number'].required = False
        self.fields['vendor_invoice_number'].label = 'Vendor invoice number'
        self.fields['notes'].required = False
        self.fields['goods_received'].label = 'Goods received'
        self.fields['goods_received'].help_text = (
            "Check if this bill is for goods already received into inventory. "
            "This will debit GRN Clearing instead of Expense."
        )
        self.fields['discount_type'].label = 'Discount type'
        self.fields['discount_value'].label = 'Discount value'
        self.fields['round_off'].label = 'Round-off'
        self.fields['round_off'].help_text = (
            'Adjustment to grand total (e.g. ±0.01 for fils rounding). Use 0 if none.'
        )
        if not self.is_bound and not self.instance.pk:
            self.fields['is_active'].initial = True
            self.fields['discount_type'].initial = 'none'
            self.fields['discount_value'].initial = Decimal('0.00')
            self.fields['round_off'].initial = Decimal('0.00')

    def clean(self):
        cleaned = super().clean()
        if self.is_bound:
            cleaned['is_active'] = 'is_active' in self.data
            cleaned['goods_received'] = 'goods_received' in self.data
        discount_type = cleaned.get('discount_type') or 'none'
        discount_value = cleaned.get('discount_value')
        round_off = cleaned.get('round_off')
        if discount_value is None:
            self.add_error('discount_value', 'Discount value is required.')
        if round_off is None:
            self.add_error('round_off', 'Round-off is required.')
        if discount_value is not None:
            if discount_type == 'none' and discount_value > 0:
                self.add_error(
                    'discount_value',
                    'Set discount value to 0 when discount type is None.',
                )
            if discount_type == 'percent' and discount_value > Decimal('100'):
                self.add_error('discount_value', 'Percentage discount cannot exceed 100.')
        goods_received = cleaned.get('goods_received', False)
        po = cleaned.get('purchase_order')

        if goods_received and not po:
            self.add_error('purchase_order',
                           'A goods-received bill must be linked to a Purchase Order.')

        if goods_received and po and po.status not in ('partial_received', 'received'):
            self.add_error(
                'purchase_order',
                f'PO {po.po_number} must be partially or fully received before a GRN-matched bill.',
            )

        project = cleaned.get('project')
        if po and po.project_id and not project:
            cleaned['project'] = po.project

        return cleaned


class VendorBillProjectForm(forms.ModelForm):
    """Change project assignment on a posted vendor bill without full edit."""

    class Meta:
        model = VendorBill
        fields = ['project']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['project'].queryset = Project.objects.filter(is_active=True).exclude(
            status='cancelled'
        ).order_by('name')
        self.fields['project'].required = False
        self.fields['project'].widget.attrs['class'] = 'form-select'
        self.fields['project'].empty_label = '— None (not charged to a project) —'


class VendorBillItemForm(forms.ModelForm):
    """
    Form for vendor bill line items.
    Tax Code determines VAT rate - No Tax Code = 0% VAT (Out of Scope)
    """
    
    class Meta:
        model = VendorBillItem
        fields = ['description', 'quantity', 'unit_price', 'tax_code', 'is_vat_inclusive', 'purchase_order_item']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.empty_permitted = True
        self.fields['description'].required = False
        self.fields['quantity'].required = False
        self.fields['unit_price'].required = False
        self.fields['purchase_order_item'].required = False
        self.fields['purchase_order_item'].widget = forms.HiddenInput()
        for field_name, field in self.fields.items():
            if field_name in ['tax_code']:
                field.widget.attrs['class'] = 'form-select'
            elif field_name == 'is_vat_inclusive':
                field.widget.attrs['class'] = 'form-check-input'
            else:
                field.widget.attrs['class'] = 'form-control'
        
        self.fields['tax_code'].queryset = TaxCode.objects.filter(is_active=True)
        self.fields['tax_code'].required = False
        self.fields['tax_code'].empty_label = "-- No Tax (Out of Scope) --"
        
        if not self.instance.pk:
            default_tax_code = TaxCode.objects.filter(is_active=True, is_default=True).first()
            if default_tax_code:
                self.fields['tax_code'].initial = default_tax_code

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('DELETE'):
            return cleaned_data

        description = (cleaned_data.get('description') or '').strip()
        unit_price = cleaned_data.get('unit_price')
        qty = cleaned_data.get('quantity')

        # Ignore blank extra rows (e.g. after removing a line in the browser).
        if not description and (qty is None or qty == 0) and (unit_price is None or unit_price == 0):
            if not self.instance.pk:
                return cleaned_data

        if not description:
            self.add_error('description', 'Description is required.')
        if not unit_price and unit_price != 0:
            self.add_error('unit_price', 'Unit price is required.')
        if qty is None or qty <= 0:
            self.add_error('quantity', 'Enter a quantity greater than zero.')
            return cleaned_data

        po_item = cleaned_data.get('purchase_order_item')
        if po_item and po_item.inventory_item_id:
            from apps.inventory.models import Item

            inv = po_item.inventory_item
            if inv.requires_whole_quantity():
                if qty != qty.to_integral_value():
                    self.add_error(
                        'quantity',
                        'Quantity must be a whole number for this item.',
                    )
                else:
                    cleaned_data['quantity'] = Item.normalize_quantity(inv, qty)
        return cleaned_data


class BaseVendorBillItemFormSet(forms.BaseInlineFormSet):
    def _is_blank_line(self, form):
        if not form.cleaned_data or form.cleaned_data.get('DELETE'):
            return True
        desc = (form.cleaned_data.get('description') or '').strip()
        qty = form.cleaned_data.get('quantity') or 0
        return not desc or qty <= 0

    def clean(self):
        super().clean()
        kept = 0
        for form in self.forms:
            if self._is_blank_line(form):
                continue
            kept += 1
        if kept == 0:
            raise forms.ValidationError('Add at least one bill line with quantity greater than zero.')

    def save_new_objects(self, commit=True):
        saved = []
        for form in self.extra_forms:
            if self._is_blank_line(form):
                continue
            saved.append(self.save_new(form, commit=commit))
        return saved


VendorBillItemFormSet = forms.inlineformset_factory(
    VendorBill,
    VendorBillItem,
    form=VendorBillItemForm,
    formset=BaseVendorBillItemFormSet,
    extra=0,
    can_delete=True
)


# ============ EXPENSE CLAIM FORMS ============

class ExpenseClaimForm(forms.ModelForm):
    """Form for creating/editing expense claims."""
    
    class Meta:
        model = ExpenseClaim
        fields = ['is_active', 'claim_date', 'description', 'project']
        widgets = {
            'claim_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'project': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        from apps.projects.models import Project

        super().__init__(*args, **kwargs)
        self.fields['is_active'].label = 'Is active'
        self.fields['is_active'].widget = forms.CheckboxInput(attrs={'class': 'form-check-input'})
        self.fields['project'].required = False
        self.fields['project'].empty_label = '— No project —'
        self.fields['project'].queryset = (
            Project.objects.filter(is_active=True)
            .exclude(status__in=['draft', 'cancelled'])
            .order_by('-start_date', '-pk')
        )
        if not self.is_bound and not self.instance.pk:
            self.fields['is_active'].initial = True

    def clean(self):
        cleaned = super().clean()
        if self.is_bound:
            cleaned['is_active'] = 'is_active' in self.data
        return cleaned


class ExpenseClaimItemForm(forms.ModelForm):
    """
    Form for expense claim line items.
    Tax Code determines VAT - No Tax Code or no receipt = 0% VAT
    """
    
    class Meta:
        model = ExpenseClaimItem
        fields = ['date', 'category', 'description', 'amount', 'tax_code', 'has_receipt', 
                  'receipt', 'is_non_deductible', 'expense_account']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        from apps.finance.models import Account
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if field_name in ['category', 'expense_account', 'tax_code']:
                field.widget.attrs['class'] = 'form-select'
            elif field_name in ['has_receipt', 'is_non_deductible']:
                field.widget.attrs['class'] = 'form-check-input'
            elif field_name != 'date':
                field.widget.attrs['class'] = 'form-control'
        
        self.fields['expense_account'].queryset = Account.objects.filter(
            is_active=True, account_type='expense'
        )
        self.fields['expense_account'].required = False
        
        # Set Tax Code queryset
        self.fields['tax_code'].queryset = TaxCode.objects.filter(is_active=True)
        self.fields['tax_code'].required = False
        self.fields['tax_code'].empty_label = "-- No Tax (Out of Scope) --"
    
    def clean(self):
        cleaned_data = super().clean()
        has_receipt = cleaned_data.get('has_receipt')
        tax_code = cleaned_data.get('tax_code')
        
        # Warn if VAT tax code selected but no receipt
        if tax_code and tax_code.rate > 0 and not has_receipt:
            # Don't raise error - just VAT won't be claimed
            pass
        
        return cleaned_data


ExpenseClaimItemFormSet = forms.inlineformset_factory(
    ExpenseClaim,
    ExpenseClaimItem,
    form=ExpenseClaimItemForm,
    extra=1,
    can_delete=True
)


class ExpenseClaimPaymentForm(forms.Form):
    """Form for paying expense claims."""
    from apps.finance.models import BankAccount
    
    bank_account = forms.ModelChoiceField(
        queryset=None,
        label='Paid from bank (Bank / Cash)',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    payment_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    payment_reference = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Check #, Transfer Ref'})
    )
    
    def __init__(self, *args, **kwargs):
        from apps.finance.models import BankAccount
        super().__init__(*args, **kwargs)
        self.fields['bank_account'].queryset = BankAccount.objects.filter(is_active=True)


# ============ RECURRING EXPENSE FORMS ============

class RecurringExpenseForm(forms.ModelForm):
    """Form for creating/editing recurring expenses."""
    
    class Meta:
        model = RecurringExpense
        fields = [
            'is_active', 'name', 'vendor', 'expense_account', 'tax_code',
            'amount', 'frequency', 'start_date', 'end_date',
            'payment_mode', 'bank_account', 'auto_post', 'description', 'status',
        ]
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        from apps.finance.models import Account, TaxCode, BankAccount
        super().__init__(*args, **kwargs)
        self.fields['is_active'].label = 'Is active'
        self.fields['is_active'].widget = forms.CheckboxInput(attrs={'class': 'form-check-input'})
        
        # Set widget classes
        for field_name, field in self.fields.items():
            if field_name in ['vendor', 'expense_account', 'tax_code', 'frequency', 
                            'payment_mode', 'bank_account', 'status']:
                field.widget.attrs['class'] = 'form-select'
            elif field_name in ['auto_post', 'is_active']:
                field.widget.attrs['class'] = 'form-check-input'
            elif 'date' not in field_name and field_name != 'description':
                field.widget.attrs['class'] = 'form-control'
        
        # Set querysets
        self.fields['vendor'].queryset = Vendor.objects.filter(is_active=True)
        self.fields['expense_account'].queryset = Account.objects.filter(
            is_active=True, account_type='expense'
        )
        self.fields['tax_code'].queryset = TaxCode.objects.filter(is_active=True)
        self.fields['tax_code'].required = False
        self.fields['bank_account'].queryset = BankAccount.objects.filter(is_active=True)
        self.fields['bank_account'].required = False
        self.fields['end_date'].required = False
        self.fields['description'].required = False
        self.fields['amount'].widget = forms.NumberInput(attrs={
            'class': 'form-control', 'step': '0.01', 'min': '0', 'id': 'recurringAmountInput',
        })
        if not self.is_bound and not self.instance.pk:
            self.fields['is_active'].initial = True
    
    def clean(self):
        cleaned_data = super().clean()
        if self.is_bound:
            cleaned_data['is_active'] = 'is_active' in self.data
        payment_mode = cleaned_data.get('payment_mode')
        bank_account = cleaned_data.get('bank_account')
        
        # Bank account required if payment mode is 'bank'
        if payment_mode == 'bank' and not bank_account:
            raise ValidationError({
                'bank_account': "Bank account is required for direct bank payment mode."
            })
        
        # End date must be after start date
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        if start_date and end_date and end_date < start_date:
            raise ValidationError({
                'end_date': "End date must be after start date."
            })
        
        return cleaned_data


# ============ DEBIT NOTES ============

class DebitNoteForm(forms.ModelForm):
    class Meta:
        model = DebitNote
        fields = [
            'is_active', 'original_bill', 'issue_date', 'vendor_credit_note_ref',
            'vendor_credit_note_date', 'reason', 'reason_description',
        ]
        widgets = {
            'issue_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'vendor_credit_note_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'reason_description': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['is_active'].label = 'Is active'
        self.fields['is_active'].widget = forms.CheckboxInput(attrs={'class': 'form-check-input'})
        self.fields['original_bill'].queryset = VendorBill.objects.filter(
            is_active=True,
            status__in=DebitNote.DEBITABLE_BILL_STATUSES,
        ).select_related('vendor').order_by('-bill_date')
        self.fields['original_bill'].widget.attrs['class'] = 'form-select'
        self.fields['reason'].widget.attrs['class'] = 'form-select'
        self.fields['vendor_credit_note_ref'].widget.attrs['class'] = 'form-control'
        self.fields['vendor_credit_note_ref'].label = 'Vendor credit note ref'
        self.fields['vendor_credit_note_date'].label = 'Vendor credit note date'
        if self.instance.pk and self.instance.status != 'draft':
            for field in self.fields.values():
                field.disabled = True
        elif not self.is_bound and not self.instance.pk:
            self.fields['is_active'].initial = True

    def clean(self):
        cleaned = super().clean()
        if self.is_bound:
            cleaned['is_active'] = 'is_active' in self.data
        bill = cleaned.get('original_bill')
        reason = cleaned.get('reason')
        reason_desc = (cleaned.get('reason_description') or '').strip()
        if reason == 'other' and not reason_desc:
            self.add_error('reason_description', 'Required when reason is Other.')
        if bill and bill.status not in DebitNote.DEBITABLE_BILL_STATUSES:
            self.add_error('original_bill', 'Only posted vendor bills can be debited.')
        return cleaned


class DebitNoteLineForm(forms.ModelForm):
    DELETE = forms.BooleanField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = DebitNoteLine
        fields = ['bill_line', 'description', 'quantity', 'DELETE']
        widgets = {
            'bill_line': forms.HiddenInput(),
            'description': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control form-control-sm text-end line-qty',
                'step': '0.01',
                'min': '0.01',
            }),
        }

    def __init__(self, *args, **kwargs):
        self.debit_note_pk = kwargs.pop('debit_note_pk', None)
        super().__init__(*args, **kwargs)
        self.fields['description'].required = False

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('DELETE'):
            return cleaned
        bill_line = cleaned.get('bill_line')
        quantity = cleaned.get('quantity')
        if bill_line and quantity is not None:
            remaining = DebitNoteLine.remaining_quantity(
                bill_line,
                exclude_debit_note_pk=self.debit_note_pk,
            )
            if quantity > remaining:
                raise ValidationError(
                    f'Quantity exceeds remaining debitable quantity ({remaining}).'
                )
        return cleaned


DebitNoteLineFormSet = inlineformset_factory(
    DebitNote,
    DebitNoteLine,
    form=DebitNoteLineForm,
    extra=0,
    can_delete=True,
    min_num=1,
    validate_min=True,
)
