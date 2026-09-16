"""
CRM Forms
"""
from django import forms
from django.core.exceptions import ValidationError

from .models import Customer, CrmLeadKanbanStage
from .customer_compliance import customer_b2b_required_missing
from .utils import (
    find_customer_contact_duplicate,
    get_crm_project_queryset,
    get_sales_employee_for_user,
    get_sales_employee_queryset,
    normalize_customer_email,
    normalize_customer_phone,
    normalize_customer_website,
    project_choice_label,
    salesperson_display_name,
)


COMPACT_CUSTOMER_FIELDS = frozenset({
    'company', 'name', 'customer_type', 'assigned_salesperson', 'business_segment',
    'email', 'phone', 'is_active', 'address', 'trn', 'website',
    'trn_document', 'trade_license_document', 'notes',
})


class CustomerForm(forms.ModelForm):
    """Form for creating/editing customers."""

    scope = forms.MultipleChoiceField(
        choices=Customer.SCOPE_CHOICES,
        required=False,
        widget=forms.SelectMultiple(
            attrs={
                'class': 'form-select select2-crm-scope',
                'data-placeholder': 'Select scope…',
            }
        ),
    )

    class Meta:
        model = Customer
        fields = [
            'is_active', 'name', 'email', 'phone', 'company', 'address', 'city', 'country',
            'trn', 'website', 'scope', 'job_type', 'primary_project',
            'payment_terms', 'credit_limit', 'status', 'customer_type', 'lead_kanban_stage',
            'assigned_salesperson', 'business_segment', 'trade_license_number',
            'trn_document', 'trade_license_document', 'notes',
        ]

    def __init__(self, *args, projects_queryset=None, user=None, compact=False, **kwargs):
        self.compact = compact
        super().__init__(*args, **kwargs)

        if compact:
            for field_name in list(self.fields.keys()):
                if field_name not in COMPACT_CUSTOMER_FIELDS:
                    del self.fields[field_name]

        qs = projects_queryset if projects_queryset is not None else get_crm_project_queryset()
        if 'primary_project' in self.fields:
            self.fields['primary_project'].queryset = qs
            self.fields['primary_project'].required = False
            self.fields['primary_project'].empty_label = '— Select project —'
            self.fields['primary_project'].label_from_instance = project_choice_label
            self.fields['primary_project'].widget.attrs['class'] = 'form-select'
            self.fields['primary_project'].label = 'Project'

        if compact:
            self.fields['is_active'].label = 'Active'
            self.fields['is_active'].widget = forms.CheckboxInput(
                attrs={'class': 'form-check-input', 'role': 'switch'}
            )
            if not self.instance.pk:
                self.initial.setdefault('is_active', False)
            self.fields['name'].label = 'Contact Name'
            self.fields['customer_type'].label = 'Type'
            self.fields['phone'].label = 'Phone'
            self.fields['trn'].label = 'VAT (TRN)'
            self.fields['trn_document'].label = 'TRN certificate'
            self.fields['trade_license_document'].label = 'Trade license'
            self.fields['assigned_salesperson'].widget.attrs['class'] = 'form-select'
        else:
            self.fields['is_active'].label = 'Is active'
            self.fields['is_active'].widget = forms.CheckboxInput(attrs={'class': 'form-check-input'})

        if 'scope' in self.fields:
            self.fields['scope'].label = 'Scope'
        self.fields['business_segment'].required = True
        self.fields['business_segment'].widget.attrs['class'] = 'form-select'
        self.fields['business_segment'].label = 'Business type'
        self.fields['trn_document'].required = False
        self.fields['trade_license_document'].required = False

        if 'lead_kanban_stage' in self.fields:
            self.fields['lead_kanban_stage'].queryset = CrmLeadKanbanStage.objects.filter(
                is_active=True,
                converts_to_customer=False,
            ).order_by('sort_order', 'id')
            self.fields['lead_kanban_stage'].required = False
            self.fields['lead_kanban_stage'].empty_label = '— Unassigned —'
            self.fields['lead_kanban_stage'].widget.attrs['class'] = 'form-select'
            self.fields['lead_kanban_stage'].label = 'Lead kanban stage'

        if 'payment_terms' in self.fields:
            self.fields['payment_terms'].widget.attrs.update({
                'class': 'form-control',
                'placeholder': 'Net 30',
            })
        if 'credit_limit' in self.fields:
            self.fields['credit_limit'].widget = forms.NumberInput(
                attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}
            )
        if 'city' in self.fields:
            self.fields['city'].widget.attrs.update({'class': 'form-control', 'placeholder': 'City'})
        if 'country' in self.fields:
            self.fields['country'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Country'})
        if 'trade_license_number' in self.fields:
            self.fields['trade_license_number'].widget.attrs.update({
                'class': 'form-control',
                'placeholder': 'Trade license number',
            })
            self.fields['trade_license_number'].label = 'Trade license number'

        include_salesperson_id = None
        if self.instance.pk and self.instance.assigned_salesperson_id:
            include_salesperson_id = self.instance.assigned_salesperson_id
        self.fields['assigned_salesperson'].queryset = get_sales_employee_queryset(
            include_employee_id=include_salesperson_id,
        )
        self.fields['assigned_salesperson'].required = True
        self.fields['assigned_salesperson'].empty_label = '— Select salesman —'
        self.fields['assigned_salesperson'].label_from_instance = salesperson_display_name
        if not compact:
            self.fields['assigned_salesperson'].widget.attrs['class'] = 'form-select select2'
        self.fields['assigned_salesperson'].label = 'Assigned salesman'
        self.fields['name'].required = False
        self.fields['company'].required = True
        self.fields['email'].required = False
        self.fields['phone'].required = False
        if not compact:
            self.fields['phone'].label = 'Contact'

        if user and not self.instance.pk:
            emp = get_sales_employee_for_user(user)
            if emp and 'assigned_salesperson' not in self.initial:
                self.initial['assigned_salesperson'] = emp.pk
            if not compact and 'country' not in self.initial:
                self.initial['country'] = 'United Arab Emirates'

        if self.instance.pk and 'scope' in self.fields:
            self.initial['scope'] = list(self.instance.scope or [])

        name_placeholder = 'Full Name (optional)' if compact else 'Contact Name'
        trn_placeholder = 'VAT / TRN' if compact else 'VAT / TRN number'

        for field_name, field in self.fields.items():
            if field_name in (
                'scope', 'primary_project', 'business_segment', 'assigned_salesperson',
                'lead_kanban_stage', 'is_active', 'payment_terms', 'credit_limit',
                'city', 'country',
            ):
                continue
            if field_name in ('trn_document', 'trade_license_document'):
                field.widget = forms.FileInput(
                    attrs={
                        'class': 'form-control',
                        'accept': '.pdf,.jpg,.jpeg,.png,.webp,.heic',
                    }
                )
                field.widget.attrs['data-crm-doc-field'] = field_name
                continue
            if field_name in ['address', 'notes']:
                field.widget.attrs['class'] = 'form-control'
                field.widget.attrs['rows'] = 3 if field_name == 'address' else 2
            elif field_name in ['status', 'customer_type', 'job_type']:
                field.widget.attrs['class'] = 'form-select'
            else:
                field.widget.attrs['class'] = 'form-control'

            if field_name == 'name':
                field.widget.attrs['placeholder'] = name_placeholder
            elif field_name == 'email':
                field.widget.attrs['placeholder'] = 'email@example.com'
            elif field_name == 'phone':
                field.widget.attrs['placeholder'] = '+971 XX XXX XXXX'
            elif field_name == 'company':
                field.widget.attrs['placeholder'] = 'Company Name'
            elif field_name == 'address':
                field.widget.attrs['placeholder'] = 'Full Address'
            elif field_name == 'trn':
                field.widget.attrs['placeholder'] = trn_placeholder
            elif field_name == 'notes':
                field.widget.attrs['placeholder'] = 'Additional notes...'
            elif field_name == 'website':
                field.widget = forms.TextInput(attrs=field.widget.attrs)
                field.widget.attrs['placeholder'] = 'gear-up.ae, www.gear-up.ae, or https://gear-up.ae'
            elif field_name == 'business_segment' and compact:
                field.widget.attrs.setdefault('id', 'crmInlineBusinessSegment')
            elif field_name == 'customer_type' and compact:
                field.widget.attrs.setdefault('id', 'crmInlineCustomerType')

    def _effective_customer_type(self):
        if self.instance.pk and self.instance.customer_type == 'customer':
            return 'customer'
        raw = self.data.get('customer_type') if self.is_bound else None
        if raw is None:
            raw = self.initial.get('customer_type', 'lead')
        return (raw or 'lead').strip()

    def clean_email(self):
        try:
            return normalize_customer_email(
                self.cleaned_data.get('email'),
                required=False,
            )
        except ValidationError as exc:
            raise forms.ValidationError(exc.messages[0] if exc.messages else str(exc))

    def clean_phone(self):
        seg = ''
        if self.data:
            seg = (self.data.get('business_segment') or '').strip().lower()
        elif self.instance.pk:
            seg = (self.instance.business_segment or '').strip().lower()
        required = seg == 'b2b'
        try:
            return normalize_customer_phone(
                self.cleaned_data.get('phone'),
                required=required,
            )
        except ValidationError as exc:
            raise forms.ValidationError(exc.messages[0] if exc.messages else str(exc))

    def clean_website(self):
        raw = self.cleaned_data.get('website') or ''
        try:
            return normalize_customer_website(raw)
        except ValidationError:
            raise forms.ValidationError(
                'Enter a valid website (e.g. gear-up.ae, www.gear-up.ae, or https://gear-up.ae).'
            )

    def clean(self):
        cleaned = super().clean()
        if self.instance.pk and self.instance.customer_type == 'customer':
            cleaned['customer_type'] = 'customer'
        seg = (cleaned.get('business_segment') or '').strip()

        if seg not in ('b2b', 'b2c'):
            self.add_error(
                'business_segment',
                'Select B2B or B2C.',
            )

        if not cleaned.get('assigned_salesperson'):
            self.add_error(
                'assigned_salesperson',
                'Select a salesman to assign this account.',
            )

        company = (cleaned.get('company') or '').strip()
        if not company:
            self.add_error('company', 'Company name is required.')
        else:
            cleaned['company'] = company

        cleaned['name'] = (cleaned.get('name') or '').strip()

        ctype = self._effective_customer_type()

        email = cleaned.get('email') or ''
        phone = cleaned.get('phone') or ''

        if seg == 'b2b':
            for field_name, label in customer_b2b_required_missing(
                business_segment=seg,
                email=email,
                phone=phone,
            ):
                self.add_error(field_name, f'{label} is required for B2B accounts.')

        if ctype == 'customer' and (email or phone):
            duplicate, matched_field = find_customer_contact_duplicate(
                email=email,
                phone=phone,
                exclude_pk=self.instance.pk if self.instance.pk else None,
            )
            if duplicate:
                label = duplicate.company or duplicate.name or duplicate.customer_number
                if matched_field == 'email':
                    self.add_error(
                        'email',
                        f'An account with this email already exists ({duplicate.customer_number} — {label}).',
                    )
                else:
                    self.add_error(
                        'phone',
                        f'An account with this phone number already exists ({duplicate.customer_number} — {label}).',
                    )

        if seg == 'b2c':
            cleaned['trn'] = ''
            if 'trade_license_number' in self.fields:
                cleaned['trade_license_number'] = ''
        elif seg == 'b2b':
            if 'trade_license_number' in self.fields:
                cleaned['trade_license_number'] = (cleaned.get('trade_license_number') or '').strip()
            if self.data.get('trn_document-clear') in ('on', 'true', '1'):
                cleaned['trn_document'] = False
            if self.data.get('trade_license_document-clear') in ('on', 'true', '1'):
                cleaned['trade_license_document'] = False

        if ctype == 'customer' and 'lead_kanban_stage' in self.fields:
            cleaned['lead_kanban_stage'] = None

        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.compact:
            instance.country = instance.country or 'United Arab Emirates'
            instance.status = 'active' if instance.is_active else 'inactive'
            seg = (self.cleaned_data.get('business_segment') or '').strip().lower()
            if seg == 'b2c':
                instance.trade_license_number = ''
            ctype = self._effective_customer_type()
            if ctype == 'customer':
                instance.lead_kanban_stage = None
        if commit:
            instance.save()
        return instance
