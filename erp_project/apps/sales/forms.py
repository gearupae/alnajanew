"""
Sales Forms - Tax Code Driven VAT (SAP/Oracle Standard)

VAT is ALWAYS derived from a TaxCode:
- No Tax Code = No VAT (Out of Scope)
- VAT rate is read-only, computed from Tax Code
"""
from django import forms
from django.contrib.auth import get_user_model
from django.forms.models import BaseInlineFormSet
from decimal import Decimal
from .models import Estimate, EstimateItem, Invoice, InvoiceItem, CreditNote, CreditNoteLine
from apps.crm.models import Customer
from apps.finance.models import TaxCode
from apps.inventory.models import ItemBaseGroup
from apps.projects.models import Project
from .estimate_csv import get_default_estimate_csv_tax_code
from .vat_pricing import default_prices_include_vat
from .invoice_project_link import get_invoice_project, save_invoice_project_link

User = get_user_model()


class EstimateForm(forms.ModelForm):
    """Form for creating/editing estimates."""

    scope = forms.MultipleChoiceField(
        choices=Estimate.SCOPE_CHOICES,
        required=False,
        label='Scope',
        widget=forms.SelectMultiple(
            attrs={
                'class': 'form-select',
                'size': '4',
            }
        ),
    )

    scope_of_work = forms.ChoiceField(
        required=False,
        label='Scope of work',
        choices=[],
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    class Meta:
        model = Estimate
        fields = [
            'is_active', 'customer', 'assigned_to', 'prepared_by', 'project',
            'scope', 'type_of_occupancy', 'type_of_work', 'scope_of_work',
            'date', 'valid_until',
            'discount_type', 'discount_value', 'prices_include_vat',
            'show_rates_on_pdf', 'show_group_totals_on_pdf',
            'show_brand_name_on_pdf',
            'notes', 'client_note', 'terms_and_conditions',
            'authorized_signature',
        ]
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d'),
            'valid_until': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d'),
            'notes': forms.Textarea(
                attrs={
                    'rows': 4,
                    'class': 'form-control estimate-internal-notes',
                    'placeholder': 'For your team only — not shown on the estimate PDF or to the client.',
                }
            ),
            'client_note': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'terms_and_conditions': forms.Textarea(attrs={'rows': 5, 'class': 'form-control'}),
            'prepared_by': forms.TextInput(attrs={'class': 'form-control'}),
            'discount_value': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'prices_include_vat': forms.CheckboxInput(
                attrs={'class': 'form-check-input', 'role': 'switch', 'id': 'id_prices_include_vat'},
            ),
            'authorized_signature': forms.FileInput(attrs={'class': 'form-control'}),
            'show_rates_on_pdf': forms.CheckboxInput(
                attrs={'class': 'form-check-input', 'role': 'switch'},
            ),
            'show_group_totals_on_pdf': forms.CheckboxInput(
                attrs={'class': 'form-check-input', 'role': 'switch'},
            ),
            'show_brand_name_on_pdf': forms.CheckboxInput(
                attrs={'class': 'form-check-input', 'role': 'switch'},
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['is_active'].label = 'Is active'
        self.fields['is_active'].widget = forms.CheckboxInput(attrs={'class': 'form-check-input'})
        self.fields['customer'].queryset = Customer.objects.filter(is_active=True)
        self.fields['customer'].label_from_instance = lambda c: c.picker_option_label
        self.fields['customer'].widget.attrs['class'] = 'form-select estimate-customer-select'
        self.fields['project'].queryset = Project.objects.filter(is_active=True).order_by('-created_at')
        self.fields['project'].required = False
        self.fields['project'].empty_label = '— Select project —'
        self.fields['project'].widget.attrs['class'] = 'form-select'
        self.fields['assigned_to'].queryset = User.objects.filter(is_active=True).order_by('first_name', 'last_name', 'username')
        self.fields['assigned_to'].widget.attrs['class'] = 'form-select'
        self.fields['assigned_to'].required = False
        self.fields['assigned_to'].label = 'Assigned to'
        self.fields['valid_until'].required = False
        self.fields['date'].input_formats = ['%Y-%m-%d']
        self.fields['valid_until'].input_formats = ['%Y-%m-%d']
        self.fields['discount_type'].widget.attrs['class'] = 'form-select'
        self.fields['notes'].required = False
        self.fields['client_note'].required = False
        self.fields['terms_and_conditions'].required = False
        self.fields['prepared_by'].required = False
        for field_name in ('type_of_occupancy', 'type_of_work'):
            field = self.fields[field_name]
            field.required = False
            field.widget.attrs['class'] = 'form-select'
        self.fields['type_of_occupancy'].label = 'Type of occupancy'
        self.fields['type_of_work'].label = 'Type of work'
        scope_choices = [('', '---------')] + [
            (name, name) for name in ItemBaseGroup.names_with_active_subgroup_items()
        ]
        if self.instance and self.instance.pk and self.instance.scope_of_work:
            current_scope = self.instance.scope_of_work
            if current_scope not in {value for value, _ in scope_choices if value}:
                scope_choices.append((current_scope, self.instance.scope_of_work_label))
        self.fields['scope_of_work'].choices = scope_choices
        self.fields['show_rates_on_pdf'].label = 'Show rates & line totals on PDF'
        self.fields['show_rates_on_pdf'].required = False
        self.fields['show_group_totals_on_pdf'].label = 'Show group totals on PDF'
        self.fields['show_group_totals_on_pdf'].required = False
        self.fields['show_brand_name_on_pdf'].label = 'Show brand name'
        self.fields['show_brand_name_on_pdf'].required = False
        self.fields['prices_include_vat'].label = 'Prices include VAT'
        self.fields['prices_include_vat'].required = False
        if not self.instance.pk and not self.is_bound:
            self.fields['show_brand_name_on_pdf'].initial = True
            self.fields['is_active'].initial = True

        if self.instance.pk:
            self.initial['scope'] = list(self.instance.scope or [])

    def clean(self):
        cleaned_data = super().clean()
        # Bootstrap switches omit unchecked boxes from POST; force explicit booleans.
        if self.is_bound:
            for field_name in (
                'is_active',
                'show_rates_on_pdf',
                'show_group_totals_on_pdf',
                'show_brand_name_on_pdf',
                'prices_include_vat',
            ):
                cleaned_data[field_name] = field_name in self.data
        project = cleaned_data.get('project')
        customer = cleaned_data.get('customer')
        if project and customer and project.customer_id and project.customer_id != customer.pk:
            self.add_error('project', 'Selected project belongs to a different customer.')
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if instance.pk:
            instance.status = Estimate.objects.values_list('status', flat=True).get(pk=instance.pk)
        if commit:
            instance.save()
        return instance


class EstimateItemForm(forms.ModelForm):
    """
    Form for estimate line items.
    Tax Code determines VAT rate - No Tax Code = 0% VAT (Out of Scope)
    """

    class Meta:
        model = EstimateItem
        fields = [
            'group_name', 'group_qty_multiplier', 'sort_order', 'inventory_item', 'description', 'quantity', 'unit_price',
            'profit_type', 'profit_value', 'rate', 'tax_code', 'is_vat_inclusive',
        ]
        widgets = {
            'group_name': forms.TextInput(attrs={
                'class': 'form-control form-control-sm item-group-name',
                'placeholder': 'PDF section',
                'list': 'estimate-group-names',
                'title': 'Estimate / PDF section title for this line. Editing this does not change inventory masters—only how this estimate is grouped on the PDF.',
            }),
            'group_qty_multiplier': forms.NumberInput(attrs={
                'class': 'form-control form-control-sm item-group-qty-mult',
                'step': '1',
                'min': '1',
                'title': 'Multiplied with qty for every line in this group (effective qty = qty × group ×).',
            }),
            'sort_order': forms.HiddenInput(),
            'description': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control form-control-sm item-qty', 'step': '1', 'min': '1'}),
            'unit_price': forms.NumberInput(attrs={'class': 'form-control form-control-sm item-base-price', 'step': '0.01', 'min': '0'}),
            'profit_type': forms.Select(attrs={'class': 'form-select form-select-sm item-profit-type'}),
            'profit_value': forms.NumberInput(attrs={'class': 'form-control form-control-sm item-profit-value', 'step': '0.01', 'min': '0'}),
            'rate': forms.NumberInput(attrs={'class': 'form-control form-control-sm item-rate', 'step': '0.01', 'readonly': 'readonly'}),
            'inventory_item': forms.Select(attrs={'class': 'form-select form-select-sm item-inventory'}),
            'is_vat_inclusive': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.inventory.models import Item

        self.fields['inventory_item'].queryset = Item.usable().order_by('name')
        self.fields['inventory_item'].required = False
        self.fields['inventory_item'].empty_label = '-- Select from inventory --'
        self.fields['description'].required = False
        self.fields['unit_price'].required = False
        self.fields['profit_value'].required = False
        self.fields['rate'].required = False

        for field_name, field in self.fields.items():
            if field_name in ['tax_code']:
                field.widget.attrs['class'] = 'form-select form-select-sm item-tax-code'
            elif field_name not in ('inventory_item', 'profit_type', 'profit_value', 'rate', 'group_name', 'group_qty_multiplier', 'sort_order', 'description', 'quantity', 'unit_price', 'is_vat_inclusive'):
                pass

        self.fields['tax_code'].queryset = TaxCode.objects.filter(is_active=True)
        self.fields['tax_code'].required = False
        self.fields['tax_code'].empty_label = "-- No Tax (Out of Scope) --"

        self.fields['profit_type'].choices = [
            ('none', 'None'),
            ('percent', 'Percent (%)'),
            ('amount', 'AED per unit'),
        ]
        self.fields['profit_value'].label = 'Profit'
        self.fields['profit_value'].help_text = 'Percent markup on base, or AED added to base per unit (not one lump for the whole line).'

        self.fields['group_name'].required = False
        self.fields['group_name'].help_text = 'Shown when this estimate is printed / on the PDF; does not update inventory.'
        self.fields['group_qty_multiplier'].required = False
        self.fields['group_qty_multiplier'].label = 'Group ×'

        if not self.instance.pk:
            default_tax_code = get_default_estimate_csv_tax_code()
            if default_tax_code:
                self.fields['tax_code'].initial = default_tax_code.pk

    def clean(self):
        cleaned = super().clean()
        inv = cleaned.get('inventory_item')
        unit_price = cleaned.get('unit_price')
        if inv and unit_price is not None:
            item = EstimateItem(
                unit_price=unit_price,
                profit_type=cleaned.get('profit_type') or 'none',
                profit_value=cleaned.get('profit_value') or Decimal('0'),
            )
            rate = item.compute_rate()
            err = inv.quote_rate_bounds_error(unit_price, rate)
            if err:
                highlight = 'profit_value' if (
                    (cleaned.get('profit_type') or 'none') != 'none'
                    and (cleaned.get('profit_value') or 0) > 0
                ) else 'unit_price'
                self.add_error(highlight, err)
        mult = cleaned.get('group_qty_multiplier')
        if mult is not None and mult < Decimal('1'):
            self.add_error('group_qty_multiplier', 'Group multiplier must be at least 1.')
        return cleaned


def estimate_line_is_empty(cleaned_data, instance=None):
    """True when a line has no inventory, description, or base price."""
    if not cleaned_data or cleaned_data.get('DELETE'):
        return False
    inv = cleaned_data.get('inventory_item')
    desc = (cleaned_data.get('description') or '').strip()
    unit_price = cleaned_data.get('unit_price')
    if unit_price is None and instance is not None:
        unit_price = instance.unit_price
    try:
        price = Decimal(str(unit_price or '0'))
    except Exception:
        price = Decimal('0')
    return not inv and not desc and price <= 0


class EstimateItemInlineFormSet(BaseInlineFormSet):
    """Hide the default DELETE checkbox; removal is done via the row ✕ (still posts DELETE)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        default_tax_code = get_default_estimate_csv_tax_code()
        if not default_tax_code:
            return
        for form in self.forms:
            if form.instance.pk:
                continue
            if form.initial.get('tax_code'):
                continue
            form.initial['tax_code'] = default_tax_code.pk
            form.fields['tax_code'].initial = default_tax_code.pk

    def clean(self):
        super().clean()
        for form in self.forms:
            if not form.cleaned_data or form.cleaned_data.get('DELETE'):
                continue
            if estimate_line_is_empty(form.cleaned_data, form.instance):
                if form.instance.pk:
                    form.cleaned_data['DELETE'] = True

    def save_new_objects(self, commit=True):
        self.new_objects = []
        for form in self.extra_forms:
            if not form.has_changed():
                continue
            if not form.cleaned_data or form.cleaned_data.get('DELETE'):
                continue
            if estimate_line_is_empty(form.cleaned_data):
                continue
            self.new_objects.append(self.save_new(form, commit=commit))
            if not commit:
                self.saved_forms.append(form)
        return self.new_objects

    def save(self, commit=True):
        # Parent estimate is saved in the view; do not re-save here (would overwrite header fields).
        return super(BaseInlineFormSet, self).save(commit=commit)

    def add_fields(self, form, index):
        super().add_fields(form, index)
        if self.can_delete and 'DELETE' in form.fields:
            form.fields['DELETE'].label = ''
            form.fields['DELETE'].widget.attrs.update(
                {'class': 'd-none', 'aria-hidden': 'true', 'tabindex': '-1'}
            )


EstimateItemFormSet = forms.inlineformset_factory(
    Estimate,
    EstimateItem,
    form=EstimateItemForm,
    formset=EstimateItemInlineFormSet,
    extra=0,
    can_delete=True,
    validate_min=False,
    min_num=0,
)


class InvoiceForm(forms.ModelForm):
    """Form for creating/editing invoices."""

    project = forms.ModelChoiceField(
        queryset=Project.objects.none(),
        required=False,
        label='Project',
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_project'}),
    )
    
    class Meta:
        model = Invoice
        fields = [
            'is_active', 'customer', 'estimate', 'invoice_date', 'due_date',
            'status', 'document_title', 'notes', 'prices_include_vat',
            'discount_type', 'discount_value', 'round_off',
        ]
        widgets = {
            'invoice_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d'),
            'due_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d'),
            'document_title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'TAX INVOICE',
                'list': 'invoice-title-suggestions',
                'id': 'id_document_title',
            }),
            'notes': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
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
        self.fields['customer'].queryset = Customer.objects.filter(is_active=True)
        self.fields['customer'].label_from_instance = lambda c: c.picker_option_label
        self.fields['customer'].widget.attrs['class'] = 'form-select estimate-customer-select'
        self.fields['customer'].widget.attrs['id'] = 'id_customer'
        self.fields['estimate'].queryset = Estimate.objects.filter(is_active=True).select_related('customer').order_by('-created_at')
        self.fields['estimate'].required = False
        self.fields['estimate'].empty_label = '— No linked estimate —'
        self.fields['estimate'].widget.attrs['class'] = 'form-select'
        self.fields['estimate'].label_from_instance = lambda est: f'{est.display_estimate_number} — {est.customer.display_name}'
        self.fields['status'].widget.attrs['class'] = 'form-select'
        self.fields['document_title'].label = 'Title bar (PDF header)'
        self.fields['document_title'].required = True
        if not self.instance.pk and not self.is_bound:
            self.fields['document_title'].initial = 'TAX INVOICE'
        self.fields['notes'].required = False
        tax_inclusive = (
            self.instance.prices_include_vat
            if self.instance.pk
            else default_prices_include_vat()
        )
        if self.is_bound:
            tax_inclusive = self.data.get('prices_include_vat') == 'yes'
        self.fields['prices_include_vat'] = forms.ChoiceField(
            choices=[('yes', 'Yes'), ('no', 'No')],
            label='Tax Inclusive',
            required=True,
            initial='yes' if tax_inclusive else 'no',
            widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_prices_include_vat'}),
            help_text='Yes = unit prices include VAT. No = prices are before VAT.',
        )
        self.fields['discount_type'].label = 'Discount type'
        self.fields['discount_value'].label = 'Discount value'
        self.fields['round_off'].label = 'Round-off'
        self.fields['round_off'].help_text = (
            'Adjustment to grand total (e.g. ±0.01 for fils rounding). Use 0 if none.'
        )
        if not self.instance.pk:
            self.fields['discount_type'].initial = 'none'
            self.fields['discount_value'].initial = Decimal('0.00')
            self.fields['round_off'].initial = Decimal('0.00')
        self.fields['invoice_date'].input_formats = ['%Y-%m-%d']
        self.fields['due_date'].input_formats = ['%Y-%m-%d']

        self.fields['project'].queryset = (
            Project.objects.filter(is_active=True)
            .exclude(status='cancelled')
            .select_related('customer')
            .order_by('-created_at')
        )
        if self.instance and self.instance.pk:
            linked = get_invoice_project(self.instance)
            if linked:
                self.fields['project'].initial = linked.pk
        elif not self.is_bound:
            self.fields['is_active'].initial = True

    def clean(self):
        cleaned = super().clean()
        if self.is_bound:
            cleaned['is_active'] = 'is_active' in self.data
            cleaned['prices_include_vat'] = self.data.get('prices_include_vat') == 'yes'
        customer = cleaned.get('customer')
        project = cleaned.get('project')
        if project and customer and project.customer_id and project.customer_id != customer.pk:
            self.add_error(
                'project',
                'Selected project belongs to a different customer.',
            )
        document_title = (cleaned.get('document_title') or '').strip()
        if not document_title:
            self.add_error('document_title', 'Title bar text is required.')
        else:
            cleaned['document_title'] = document_title
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
        return cleaned

    def save(self, commit=True):
        invoice = super().save(commit=commit)
        if commit:
            project = self.cleaned_data.get('project')
            if not project and invoice.estimate_id:
                from .invoice_project_link import resolve_estimate_project

                project = resolve_estimate_project(invoice.estimate)
            save_invoice_project_link(invoice, project)
        return invoice


class InvoiceItemForm(forms.ModelForm):
    """
    Form for invoice line items.
    Tax Code determines VAT rate - No Tax Code = 0% VAT (Out of Scope)
    """
    
    class Meta:
        model = InvoiceItem
        fields = ['description', 'quantity', 'unit_price', 'tax_code', 'is_vat_inclusive']
        widgets = {
            'is_vat_inclusive': forms.HiddenInput(),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['description'].required = False
        self.fields['unit_price'].required = False
        for field_name, field in self.fields.items():
            if field_name in ['tax_code']:
                field.widget.attrs['class'] = 'form-select'
            else:
                field.widget.attrs['class'] = 'form-control'
        
        self.fields['tax_code'].queryset = TaxCode.objects.filter(is_active=True)
        self.fields['tax_code'].required = False
        self.fields['tax_code'].empty_label = "-- No Tax (Out of Scope) --"
        
        if not self.instance.pk:
            default_tax_code = get_default_estimate_csv_tax_code()
            if default_tax_code:
                self.fields['tax_code'].initial = default_tax_code.pk

    def clean(self):
        cleaned_data = super().clean()
        description = (cleaned_data.get('description') or '').strip()
        unit_price = cleaned_data.get('unit_price')
        if not description and not unit_price:
            return cleaned_data
        if not description:
            self.add_error('description', 'Description is required.')
        if not unit_price and unit_price != 0:
            self.add_error('unit_price', 'Unit price is required.')
        return cleaned_data


InvoiceItemFormSet = forms.inlineformset_factory(
    Invoice,
    InvoiceItem,
    form=InvoiceItemForm,
    extra=1,
    can_delete=True,
    validate_min=False,
    min_num=0
)


# ============ TAX CREDIT NOTES ============

class CreditNoteForm(forms.ModelForm):
    class Meta:
        model = CreditNote
        fields = [
            'is_active', 'original_invoice', 'issue_date', 'trigger_event_date',
            'reason', 'reason_description',
        ]
        widgets = {
            'issue_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'trigger_event_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'reason_description': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['is_active'].label = 'Is active'
        self.fields['is_active'].widget = forms.CheckboxInput(attrs={'class': 'form-check-input'})
        self.fields['original_invoice'].queryset = Invoice.objects.filter(
            is_active=True,
            status__in=CreditNote.CREDITABLE_INVOICE_STATUSES,
        ).select_related('customer').order_by('-invoice_date')
        self.fields['original_invoice'].widget.attrs['class'] = 'form-select'
        self.fields['reason'].widget.attrs['class'] = 'form-select'
        self.fields['reason_description'].widget.attrs['class'] = 'form-control'
        if self.instance.pk and self.instance.status != 'draft':
            for field in self.fields.values():
                field.disabled = True
        elif not self.is_bound and not self.instance.pk:
            self.fields['is_active'].initial = True

    def clean(self):
        cleaned = super().clean()
        if self.is_bound:
            cleaned['is_active'] = 'is_active' in self.data
        invoice = cleaned.get('original_invoice')
        issue_date = cleaned.get('issue_date')
        trigger_date = cleaned.get('trigger_event_date')
        reason = cleaned.get('reason')
        reason_desc = (cleaned.get('reason_description') or '').strip()
        if reason == 'other' and not reason_desc:
            self.add_error('reason_description', 'Required when reason is Other.')
        if invoice and invoice.status not in CreditNote.CREDITABLE_INVOICE_STATUSES:
            self.add_error('original_invoice', 'Only posted invoices can be credited.')
        if issue_date and trigger_date and issue_date < trigger_date:
            self.add_error('issue_date', 'Issue date cannot be before the trigger event date.')
        return cleaned

