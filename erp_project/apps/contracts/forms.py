from django import forms

from apps.crm.models import Customer
from apps.settings_app.models import CompanySettings

from .models import Contract, ContractType


class ContractTypeForm(forms.ModelForm):
    class Meta:
        model = ContractType
        fields = ['is_active', 'name', 'slug']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['is_active'].label = 'Is active'
        self.fields['is_active'].widget = forms.CheckboxInput(attrs={'class': 'form-check-input'})
        if not self.instance.pk:
            self.fields['is_active'].initial = True
        self.fields['slug'].required = False
        self.fields['slug'].help_text = 'Optional; auto-generated from name when left blank.'
        for name, field in self.fields.items():
            if name == 'is_active':
                continue
            field.widget.attrs['class'] = 'form-control'

    def clean(self):
        cleaned = super().clean()
        if self.data:
            cleaned['is_active'] = 'is_active' in self.data
        elif not self.instance.pk:
            cleaned['is_active'] = True
        return cleaned


class ContractForm(forms.ModelForm):
    class Meta:
        model = Contract
        fields = [
            'is_active',
            'customer',
            'name',
            'contract_value',
            'start_date',
            'end_date',
            'status',
            'remind_before_days',
            'description',
            'scope_of_work',
            'terms_and_conditions',
            'contract_types',
        ]
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
            'customer': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Contract name'}),
            'contract_value': forms.NumberInput(attrs={'class': 'form-control', 'step': '1', 'min': '0'}),
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'remind_before_days': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'max': '365'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'scope_of_work': forms.HiddenInput(),
            'terms_and_conditions': forms.Textarea(
                attrs={'rows': 6, 'class': 'form-control', 'placeholder': 'Terms & conditions (shown on PDF)'}
            ),
            'contract_types': forms.SelectMultiple(
                attrs={'class': 'form-select select2-contract-types', 'data-placeholder': 'Select types…'}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['is_active'].label = 'Is active'
        self.fields['is_active'].widget = forms.CheckboxInput(attrs={'class': 'form-check-input'})
        if not self.instance.pk:
            self.fields['is_active'].initial = True
            self.fields['status'].initial = 'draft'

        self.fields['customer'].queryset = Customer.objects.filter(is_active=True).order_by('name', 'company')
        self.fields['customer'].required = False
        self.fields['customer'].empty_label = '— No customer —'
        self.fields['contract_types'].queryset = ContractType.objects.filter(is_active=True).order_by('name')
        self.fields['contract_types'].required = False
        self.fields['contract_types'].label = 'Contract types'
        self.fields['contract_value'].label = 'Contract value'
        self.fields['remind_before_days'].label = 'Remind before (days)'
        self.fields['status'].label = 'Status'
        self.fields['terms_and_conditions'].label = 'Terms & conditions'
        self.fields['scope_of_work'].required = False
        if not self.instance.pk and not self.data:
            self.fields['terms_and_conditions'].initial = (
                CompanySettings.get_settings().contract_default_terms or ''
            )

    def clean(self):
        cleaned = super().clean()
        if self.data:
            cleaned['is_active'] = 'is_active' in self.data
        elif not self.instance.pk:
            cleaned['is_active'] = True
        start = cleaned.get('start_date')
        end = cleaned.get('end_date')
        if start and end and end < start:
            raise forms.ValidationError('End date must be on or after start date.')
        lines = []
        if self.data:
            lines = [line.strip() for line in self.data.getlist('scope_of_work_line') if line.strip()]
        cleaned['scope_of_work'] = '\n'.join(lines)
        return cleaned


def scope_of_work_lines_for_context(form, instance=None):
    """Bullet rows for the scope-of-work UI."""
    if form is not None and form.data and 'scope_of_work_line' in form.data:
        lines = [line.strip() for line in form.data.getlist('scope_of_work_line')]
        return lines or ['']
    if instance is not None and getattr(instance, 'pk', None):
        lines = instance.scope_of_work_lines
        return lines or ['']
    return ['']
