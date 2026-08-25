"""
Property Management Forms - PDC & Bank Reconciliation
"""
from django import forms
from django.core.exceptions import ValidationError
from decimal import Decimal

from .models import (
    Property, Unit, Tenant, Lease, PDCCheque,
    PDCAllocation, PDCAllocationLine,
    RentInvoice, SecurityDeposit,
)


def _apply_is_active_checkbox(form):
    form.fields['is_active'].label = 'Is active'
    form.fields['is_active'].widget = forms.CheckboxInput(attrs={'class': 'form-check-input'})
    if not form.instance.pk:
        form.fields['is_active'].initial = True


def _clean_is_active(form, cleaned):
    if form.data:
        cleaned['is_active'] = 'is_active' in form.data
    elif not form.instance.pk:
        cleaned['is_active'] = True
    return cleaned


class PropertyForm(forms.ModelForm):
    class Meta:
        model = Property
        fields = [
            'is_active', 'name', 'address', 'city', 'emirate', 'country',
            'property_type', 'total_units', 'description', 'ar_account',
        ]
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_is_active_checkbox(self)
        for name, field in self.fields.items():
            if name == 'is_active':
                continue
            if name in ('property_type', 'ar_account'):
                field.widget.attrs['class'] = 'form-select'
            elif name not in self.Meta.widgets:
                field.widget.attrs['class'] = 'form-control'

    def clean(self):
        return _clean_is_active(self, super().clean())


class UnitForm(forms.ModelForm):
    class Meta:
        model = Unit
        fields = [
            'is_active', 'property', 'unit_number', 'unit_type', 'floor',
            'area_sqft', 'bedrooms', 'bathrooms', 'status', 'monthly_rent',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_is_active_checkbox(self)
        self.fields['property'].queryset = Property.objects.filter(is_active=True).order_by('name')
        for name, field in self.fields.items():
            if name == 'is_active':
                continue
            field.widget.attrs['class'] = 'form-select' if name in ('property', 'unit_type', 'status') else 'form-control'

    def clean(self):
        return _clean_is_active(self, super().clean())


class TenantForm(forms.ModelForm):
    class Meta:
        model = Tenant
        fields = [
            'is_active', 'name', 'email', 'phone', 'mobile', 'company',
            'emirates_id', 'trade_license', 'trn',
            'address', 'city', 'country', 'status', 'ar_account', 'notes',
        ]
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_is_active_checkbox(self)
        self.fields['trn'].label = 'Tax Registration Number'
        for name, field in self.fields.items():
            if name == 'is_active':
                continue
            if name in ('status', 'ar_account'):
                field.widget.attrs['class'] = 'form-select'
            elif name not in self.Meta.widgets:
                field.widget.attrs['class'] = 'form-control'

    def clean(self):
        return _clean_is_active(self, super().clean())


class LeaseForm(forms.ModelForm):
    class Meta:
        model = Lease
        fields = [
            'is_active', 'unit', 'tenant', 'start_date', 'end_date',
            'annual_rent', 'payment_frequency', 'number_of_cheques',
            'security_deposit', 'deposit_paid', 'status',
            'ejari_number', 'ejari_registered', 'notes',
        ]
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_is_active_checkbox(self)
        self.fields['tenant'].queryset = Tenant.objects.filter(is_active=True).order_by('name')
        self.fields['unit'].queryset = Unit.objects.filter(is_active=True).select_related('property').order_by(
            'property__name', 'unit_number'
        )
        self.fields['unit'].required = False
        self.fields['deposit_paid'].widget = forms.CheckboxInput(attrs={'class': 'form-check-input'})
        self.fields['ejari_registered'].widget = forms.CheckboxInput(attrs={'class': 'form-check-input'})
        for name, field in self.fields.items():
            if name in ('is_active', 'deposit_paid', 'ejari_registered'):
                continue
            if name in self.Meta.widgets:
                continue
            field.widget.attrs['class'] = 'form-select' if name in ('unit', 'tenant', 'payment_frequency', 'status') else 'form-control'

    def clean(self):
        cleaned = _clean_is_active(self, super().clean())
        if self.data:
            cleaned['deposit_paid'] = 'deposit_paid' in self.data
            cleaned['ejari_registered'] = 'ejari_registered' in self.data
        return cleaned


class PDCChequeForm(forms.ModelForm):
    class Meta:
        model = PDCCheque
        fields = [
            'is_active', 'tenant', 'lease', 'cheque_number', 'bank_name', 'cheque_date',
            'amount', 'drawer_name', 'drawer_account', 'purpose',
            'payment_period_start', 'payment_period_end', 'notes',
        ]
        widgets = {
            'cheque_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'payment_period_start': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'payment_period_end': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_is_active_checkbox(self)
        self.fields['tenant'].queryset = Tenant.objects.filter(is_active=True).order_by('name')
        self.fields['lease'].queryset = Lease.objects.filter(is_active=True).select_related('tenant').order_by('-start_date')
        self.fields['lease'].required = False
        for name, field in self.fields.items():
            if name == 'is_active':
                continue
            if name in self.Meta.widgets:
                continue
            field.widget.attrs['class'] = 'form-select' if name in ('tenant', 'lease', 'purpose') else 'form-control'

    def clean(self):
        cleaned = _clean_is_active(self, super().clean())
        cheque_number = cleaned.get('cheque_number')
        bank_name = cleaned.get('bank_name')
        cheque_date = cleaned.get('cheque_date')
        amount = cleaned.get('amount')
        tenant = cleaned.get('tenant')

        if cheque_number and bank_name and cheque_date and amount and tenant:
            existing = PDCCheque.objects.filter(
                cheque_number=cheque_number,
                bank_name=bank_name,
                cheque_date=cheque_date,
                amount=amount,
                tenant=tenant,
                is_active=True,
            )
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise ValidationError(
                    'A PDC with the same cheque number, bank, date, amount, and tenant already exists.'
                )
        return cleaned


class PDCDepositForm(forms.Form):
    bank_account = forms.ModelChoiceField(
        queryset=None,
        label='Deposit to Bank',
        help_text='Select the bank account to deposit this cheque',
    )
    deposit_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        help_text='Date of deposit',
    )

    def __init__(self, *args, **kwargs):
        from apps.finance.models import BankAccount
        super().__init__(*args, **kwargs)
        self.fields['bank_account'].queryset = BankAccount.objects.filter(is_active=True)


class PDCClearForm(forms.Form):
    clearing_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        help_text='Date cheque was cleared by bank',
    )
    clearing_reference = forms.CharField(
        max_length=100,
        required=False,
        help_text='Bank reference number for clearing',
    )


class PDCBounceForm(forms.Form):
    bounce_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date'}),
        help_text='Date cheque bounced',
    )
    bounce_reason = forms.CharField(
        max_length=200,
        required=True,
        help_text='Reason for bounce (e.g., Insufficient Funds, Signature Mismatch)',
    )
    bounce_charges = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        initial=Decimal('0.00'),
        required=False,
        help_text='Bounce charges to be recovered from tenant',
    )


class PDCAllocationForm(forms.ModelForm):
    class Meta:
        model = PDCAllocation
        fields = ['allocation_date', 'reason', 'notes']
        widgets = {
            'allocation_date': forms.DateInput(attrs={'type': 'date'}),
            'reason': forms.Textarea(attrs={'rows': 3}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }


class PDCAllocationLineForm(forms.ModelForm):
    class Meta:
        model = PDCAllocationLine
        fields = ['pdc', 'amount', 'notes']

    def __init__(self, *args, bank_statement_line=None, **kwargs):
        super().__init__(*args, **kwargs)
        if bank_statement_line:
            self.fields['pdc'].queryset = PDCCheque.objects.filter(
                status='deposited',
                deposit_status='in_clearing',
                deposited_to_bank=bank_statement_line.statement.bank_account,
                is_active=True,
            )


class PDCAllocationLineFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return

        total_allocated = Decimal('0.00')
        pdcs_used = set()

        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                pdc = form.cleaned_data.get('pdc')
                amount = form.cleaned_data.get('amount', Decimal('0.00'))

                if pdc:
                    if pdc.pk in pdcs_used:
                        raise ValidationError(f'PDC {pdc.pdc_number} is allocated multiple times.')
                    pdcs_used.add(pdc.pk)

                    if amount > pdc.amount:
                        raise ValidationError(
                            f'Allocated amount ({amount}) exceeds PDC amount ({pdc.amount}) for {pdc.pdc_number}'
                        )

                    total_allocated += amount

        return total_allocated


class BankStatementMatchForm(forms.Form):
    match_by_amount = forms.BooleanField(required=False, initial=True)
    match_by_date = forms.BooleanField(required=False, initial=True)
    match_by_cheque_number = forms.BooleanField(required=False, initial=False)
    date_tolerance_days = forms.IntegerField(
        initial=3,
        min_value=0,
        max_value=30,
        help_text='Number of days tolerance for date matching',
    )


class BulkPDCForm(forms.Form):
    lease = forms.ModelChoiceField(
        queryset=Lease.objects.filter(is_active=True, status='active'),
        label='Select Lease',
    )
    bank_name = forms.CharField(max_length=200)
    first_cheque_number = forms.CharField(max_length=50)
    drawer_name = forms.CharField(max_length=200, required=False)
    drawer_account = forms.CharField(max_length=50, required=False)
    notes = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 2}),
        required=False,
    )

    def clean_first_cheque_number(self):
        value = self.cleaned_data['first_cheque_number']
        try:
            int(value)
        except ValueError:
            raise ValidationError('First cheque number must be numeric for auto-increment.')
        return value


class RentInvoiceForm(forms.ModelForm):
    class Meta:
        model = RentInvoice
        fields = [
            'tenant', 'lease', 'unit', 'invoice_date', 'due_date',
            'period_start', 'period_end', 'rent_amount', 'vat_rate', 'pdc', 'notes',
        ]
        widgets = {
            'invoice_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'due_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'period_start': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'period_end': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        lease = kwargs.pop('lease', None)
        super().__init__(*args, **kwargs)
        self.fields['tenant'].queryset = Tenant.objects.filter(is_active=True).order_by('name')
        self.fields['lease'].queryset = Lease.objects.filter(is_active=True).select_related('tenant')
        self.fields['unit'].queryset = Unit.objects.filter(is_active=True).select_related('property')
        self.fields['lease'].required = False
        self.fields['unit'].required = False
        self.fields['pdc'].required = False
        self.fields['pdc'].queryset = PDCCheque.objects.filter(is_active=True).select_related('tenant')
        for name, field in self.fields.items():
            if name in self.Meta.widgets:
                continue
            field.widget.attrs['class'] = 'form-select' if name in (
                'tenant', 'lease', 'unit', 'pdc'
            ) else 'form-control'
        if lease and not self.instance.pk:
            self.fields['tenant'].initial = lease.tenant_id
            self.fields['lease'].initial = lease.pk
            self.fields['unit'].initial = lease.unit_id
            from .property_billing import vat_rate_for_lease
            self.fields['vat_rate'].initial = vat_rate_for_lease(lease)
            self.fields['rent_amount'].initial = lease.payment_amount


class SecurityDepositReceiveForm(forms.Form):
    bank_account = forms.ModelChoiceField(queryset=None, label='Bank account')
    receive_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
    )
    amount = forms.DecimalField(
        max_digits=12, decimal_places=2, required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
    )

    def __init__(self, *args, deposit=None, **kwargs):
        from apps.finance.models import BankAccount
        super().__init__(*args, **kwargs)
        self.fields['bank_account'].queryset = BankAccount.objects.filter(is_active=True)
        self.fields['bank_account'].widget.attrs['class'] = 'form-select'
        if deposit:
            self.fields['amount'].initial = deposit.amount


class SecurityDepositRefundForm(forms.Form):
    refund_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
    )
    refund_amount = forms.DecimalField(
        max_digits=12, decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
    )
    forfeit_amount = forms.DecimalField(
        max_digits=12, decimal_places=2, initial=Decimal('0.00'), required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
    )
    reason = forms.CharField(
        max_length=200, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
