from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Prefetch
from decimal import Decimal
from .models import Project, Task, ProjectExpense, ProjectGatepass, ProjectItemLine
from .member_roles import get_project_source_estimate
from apps.crm.models import Customer
from apps.inventory.models import Item
from apps.purchase.models import Vendor
from apps.finance.models import Account
from apps.sales.models import Estimate
from django.contrib.auth import get_user_model

User = get_user_model()


def project_staff_choice_label(user):
    """Display name + HR employee code in Members / Technicians dropdowns."""
    name = (user.get_full_name() or '').strip()
    emp = getattr(user, 'employee_profile', None)
    if emp:
        if not name:
            name = emp.full_name
        code = (emp.employee_code or '').strip()
        if name and code:
            return f'{name} — {code}'
        if code:
            return code
    if name:
        return name
    return user.username


def _project_customer_display_name(customer):
    if not customer:
        return ''
    return (customer.company or customer.name or '').strip()


def project_expense_choice_label(project):
    """Project code, linked estimate number, and customer name from that estimate."""
    parts = [project.project_code]
    estimate = get_project_source_estimate(project)
    if estimate:
        est_num = getattr(estimate, 'display_estimate_number', None) or estimate.estimate_number
        parts.append(est_num)
        customer_name = _project_customer_display_name(estimate.customer)
        if customer_name:
            parts.append(customer_name)
    else:
        customer_name = _project_customer_display_name(project.customer)
        if customer_name:
            parts.append(customer_name)
        elif project.name:
            parts.append(project.name)
    return ' - '.join(parts)


def project_staff_select_queryset():
    """
    Every user account for Members / Technicians.

    Project membership is stored against Django users; HR may list more people than
    have (or have active) logins — we still expose **all** ``User`` rows so nothing
    is hidden by ``is_active`` or HR link state. Active accounts sort first.
    """
    return (
        User.objects.select_related('employee_profile')
        .all()
        .order_by('-is_active', 'first_name', 'last_name', 'username')
    )


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = [
            'is_active', 'name', 'description', 'customer', 'manager', 'status',
            'start_date', 'end_date', 'billing_type', 'budget', 'estimated_cost',
            'contract_value', 'expense_account', 'revenue_account',
            'members', 'technicians',
        ]
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 2}),
            'members': forms.SelectMultiple(
                attrs={'class': 'form-select select2-members', 'data-placeholder': 'Search by name or employee code…'}
            ),
            'technicians': forms.SelectMultiple(
                attrs={'class': 'form-select select2-technicians', 'data-placeholder': 'Search by name or employee code…'}
            ),
        }

    def __init__(self, *args, **kwargs):
        from apps.finance.models import Account

        super().__init__(*args, **kwargs)
        self.fields['is_active'].label = 'Is active'
        self.fields['is_active'].widget = forms.CheckboxInput(attrs={'class': 'form-check-input'})
        if not self.instance.pk:
            self.fields['is_active'].initial = True
        staff_qs = project_staff_select_queryset()
        manager_qs = User.objects.filter(is_active=True).order_by('first_name', 'last_name', 'username')
        self.fields['manager'].queryset = manager_qs
        self.fields['members'].queryset = staff_qs
        self.fields['members'].required = False
        self.fields['members'].label = 'Members'
        self.fields['members'].label_from_instance = project_staff_choice_label
        self.fields['technicians'].queryset = staff_qs
        self.fields['technicians'].required = False
        self.fields['technicians'].label = 'Technicians'
        self.fields['technicians'].label_from_instance = project_staff_choice_label
        self.fields['expense_account'].queryset = Account.objects.filter(
            is_active=True, account_type__in=['expense', 'cogs']
        )
        self.fields['expense_account'].required = False
        self.fields['expense_account'].empty_label = '— Use default —'
        self.fields['revenue_account'].queryset = Account.objects.filter(
            is_active=True, account_type='income'
        )
        self.fields['revenue_account'].required = False
        self.fields['revenue_account'].empty_label = '— Use default —'
        for name, field in self.fields.items():
            if name in ['customer', 'manager', 'status', 'billing_type', 'expense_account', 'revenue_account']:
                field.widget.attrs['class'] = 'form-select'
            elif name in ('members', 'technicians', 'is_active'):
                pass
            else:
                field.widget.attrs['class'] = 'form-control'
        self.fields['budget'].widget.attrs.setdefault('step', '0.01')
        self.fields['estimated_cost'].widget.attrs.setdefault('step', '0.01')
        self.fields['contract_value'].widget.attrs.setdefault('step', '0.01')

        from .conversion_approval import project_awaiting_conversion_approval

        if self.instance.pk and project_awaiting_conversion_approval(self.instance):
            self.fields['status'].disabled = True
            self.fields['status'].help_text = (
                'Status stays Draft until a configured approver approves the conversion from quotation.'
            )

    def clean(self):
        cleaned = super().clean()
        if self.data:
            cleaned['is_active'] = 'is_active' in self.data
        return cleaned

    def clean_status(self):
        from .conversion_approval import project_awaiting_conversion_approval

        status = self.cleaned_data.get('status')
        if self.instance.pk and project_awaiting_conversion_approval(self.instance):
            return 'draft'
        return status


class CustomerTaskCreateForm(forms.Form):
    """Quick task create from CRM customer detail (one task per selected member)."""

    name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Task name'}),
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Task description'}),
    )
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
    )
    due_date = forms.DateField(
        required=False,
        label='End date',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
    )
    members = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        widget=forms.SelectMultiple(
            attrs={
                'class': 'form-select select2-task-members',
                'data-placeholder': 'Search by name or employee code…',
            }
        ),
        label='Members',
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        staff_qs = project_staff_select_queryset()
        self.fields['members'].queryset = staff_qs
        self.fields['members'].label_from_instance = project_staff_choice_label

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get('start_date')
        end = cleaned.get('due_date')
        if start and end and start > end:
            raise ValidationError('Start date must be on or before end date.')
        return cleaned


class ProjectTaskCreateForm(CustomerTaskCreateForm):
    """Quick task create from project detail (one task per selected member)."""

    status = forms.ChoiceField(
        choices=Task.STATUS_CHOICES,
        initial='pending',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    priority = forms.ChoiceField(
        choices=Task.PRIORITY_CHOICES,
        initial='medium',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    estimated_hours = forms.DecimalField(
        required=False,
        initial=Decimal('0.00'),
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '1', 'min': '0'}),
    )


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = [
            'is_active', 'project', 'customer', 'name', 'description',
            'assigned_to', 'status', 'priority', 'start_date', 'due_date',
            'estimated_hours',
        ]
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'due_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
            'estimated_hours': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
        }

    def __init__(self, *args, project=None, customer=None, **kwargs):
        self.project = project
        self.customer = customer
        super().__init__(*args, **kwargs)

        self.fields['is_active'].label = 'Is active'
        self.fields['is_active'].widget = forms.CheckboxInput(attrs={'class': 'form-check-input'})
        if not self.instance.pk:
            self.fields['is_active'].initial = True

        self.fields['customer'].label = 'Customer / lead'
        self.fields['project'].queryset = (
            Project.objects.filter(is_active=True).order_by('project_code', 'name')
        )
        self.fields['customer'].queryset = (
            Customer.objects.filter(is_active=True).order_by('customer_number', 'name')
        )
        self.fields['project'].required = False
        self.fields['customer'].required = False
        self.fields['project'].empty_label = '-- None --'
        self.fields['customer'].empty_label = '-- None --'

        self.fields['assigned_to'].queryset = (
            User.objects.filter(is_active=True)
            .select_related('employee_profile')
            .order_by('first_name', 'last_name', 'username')
        )
        self.fields['assigned_to'].required = False
        self.fields['assigned_to'].empty_label = '-- Unassigned --'
        self.fields['assigned_to'].label_from_instance = project_staff_choice_label
        self.fields['due_date'].label = 'End date'
        self.fields['start_date'].label = 'Start date'
        self.fields['estimated_hours'].label = 'Estimated hours'

        for name, field in self.fields.items():
            if name == 'is_active':
                continue
            if name in ['assigned_to', 'status', 'priority', 'project', 'customer']:
                field.widget.attrs['class'] = 'form-select'
            else:
                field.widget.attrs['class'] = 'form-control'

        if project is not None:
            self.fields['project'].initial = project.pk
            self.fields['project'].disabled = True
            if project.customer_id:
                self.fields['customer'].initial = project.customer_id
                self.fields['customer'].disabled = True
        elif customer is not None:
            self.fields['customer'].initial = customer.pk
            self.fields['customer'].disabled = True

    def clean(self):
        cleaned = super().clean()
        if self.data:
            cleaned['is_active'] = 'is_active' in self.data

        if self.project is not None:
            cleaned['project'] = self.project
            if self.project.customer_id:
                cleaned['customer'] = self.project.customer
        elif self.customer is not None:
            cleaned['customer'] = self.customer

        start = cleaned.get('start_date')
        end = cleaned.get('due_date')
        if start and end and start > end:
            raise ValidationError('Start date must be on or before end date.')

        if not cleaned.get('project') and not cleaned.get('customer'):
            raise ValidationError('Task must be linked to a project or a customer/lead.')
        return cleaned

    def _post_clean(self):
        if self.project is not None:
            self.instance.project = self.project
            if self.project.customer_id:
                self.instance.customer = self.project.customer
        elif self.customer is not None:
            self.instance.customer = self.customer
        super()._post_clean()


class ProjectGatepassForm(forms.ModelForm):
    class Meta:
        model = ProjectGatepass
        fields = ['member', 'start_date', 'expiry_date', 'reference_number', 'notes']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'expiry_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, project=None, **kwargs):
        self.project = project
        super().__init__(*args, **kwargs)
        if project is not None:
            from django.contrib.auth import get_user_model

            User = get_user_model()
            team_ids = set(project.members.values_list('pk', flat=True))
            team_ids |= set(project.technicians.values_list('pk', flat=True))
            self.fields['member'].queryset = User.objects.filter(pk__in=team_ids).order_by(
                'first_name', 'last_name', 'username'
            )
        self.fields['member'].label = 'Team member / technician'
        self.fields['expiry_date'].label = 'Expiry date'
        for name, field in self.fields.items():
            if name == 'member':
                field.widget.attrs['class'] = 'form-select'
            else:
                field.widget.attrs.setdefault('class', 'form-control')

    def clean(self):
        cleaned = super().clean()
        if self.project and cleaned.get('member'):
            allowed = set(self.project.members.values_list('pk', flat=True))
            allowed |= set(self.project.technicians.values_list('pk', flat=True))
            if cleaned['member'].pk not in allowed:
                raise ValidationError('Selected person must belong to this project team.')
        start = cleaned.get('start_date')
        end = cleaned.get('expiry_date')
        if start and end and start > end:
            raise ValidationError('Start date must be on or before expiry date.')
        return cleaned


class ProjectExpenseForm(forms.ModelForm):
    """Form for creating/editing project expenses."""
    class Meta:
        model = ProjectExpense
        fields = [
            'is_active', 'project', 'category', 'description', 'expense_date',
            'amount', 'vat_amount', 'vendor', 'invoice_reference', 'expense_account',
        ]
        widgets = {
            'expense_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['is_active'].label = 'Is active'
        self.fields['is_active'].widget = forms.CheckboxInput(attrs={'class': 'form-check-input'})
        if not self.instance.pk:
            self.fields['is_active'].initial = True

        estimate_qs = (
            Estimate.objects.filter(is_active=True)
            .select_related('customer')
            .order_by('-date', '-pk')
        )
        self.fields['project'].queryset = (
            Project.objects.filter(is_active=True)
            .exclude(status='cancelled')
            .select_related('customer')
            .prefetch_related(Prefetch('estimates', queryset=estimate_qs))
            .order_by('-created_at', '-pk')
        )
        self.fields['project'].label_from_instance = project_expense_choice_label
        self.fields['project'].widget.attrs['class'] = 'form-select select2-project'
        self.fields['project'].widget.attrs['data-placeholder'] = 'Search by code or customer…'

        self.fields['vendor'].queryset = Vendor.objects.filter(is_active=True)
        self.fields['vendor'].required = False

        self.fields['expense_account'].queryset = Account.objects.filter(
            is_active=True,
            account_type__in=['expense', 'cogs'],
        )
        self.fields['expense_account'].required = False
        self.fields['expense_account'].empty_label = '-- Use Default --'

        for name, field in self.fields.items():
            if name == 'is_active':
                continue
            if name in ['category', 'vendor', 'expense_account']:
                field.widget.attrs['class'] = 'form-select'
            elif name == 'project':
                pass
            else:
                field.widget.attrs['class'] = 'form-control'

        self.fields['amount'].widget.attrs['step'] = '0.01'
        self.fields['vat_amount'].widget.attrs['step'] = '0.01'

        if self.instance.pk and self.instance.vendor_bill_id:
            for field_name in ('project', 'amount', 'vat_amount', 'vendor', 'invoice_reference'):
                self.fields[field_name].disabled = True
                self.fields[field_name].help_text = 'Managed from the linked vendor bill.'

    def clean(self):
        cleaned = super().clean()
        if self.data:
            cleaned['is_active'] = 'is_active' in self.data

        if self.instance.pk and self.instance.vendor_bill_id:
            cleaned['project'] = self.instance.project
            cleaned['amount'] = self.instance.amount
            cleaned['vat_amount'] = self.instance.vat_amount
            cleaned['vendor'] = self.instance.vendor
            cleaned['invoice_reference'] = self.instance.invoice_reference
        return cleaned


class ProjectItemDeliveryForm(forms.Form):
    """Deliver inventory items to a project (FIFO for serial-tracked items)."""

    item = forms.ModelChoiceField(
        queryset=Item.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        empty_label='Select item…',
    )
    quantity = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        min_value=Decimal('1'),
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '1', 'min': '1'}),
    )
    delivered_date = forms.DateField(
        label='Delivered date',
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
    )

    def __init__(self, *args, project=None, **kwargs):
        self.project = project
        super().__init__(*args, **kwargs)

        if project is None:
            self.fields['project'] = forms.ModelChoiceField(
                queryset=(
                    Project.objects.filter(is_active=True)
                    .exclude(status='cancelled')
                    .order_by('project_code', 'name')
                ),
                widget=forms.Select(attrs={'class': 'form-select select2-project'}),
                empty_label='Select project…',
            )
        else:
            project_field = forms.ModelChoiceField(
                queryset=Project.objects.filter(pk=project.pk),
                initial=project.pk,
                widget=forms.Select(attrs={'class': 'form-select'}),
            )
            project_field.disabled = True
            self.fields['project'] = project_field

        qs = Item.objects.filter(is_active=True, item_type='product').order_by('name')
        active_project = project
        if active_project is None and self.data.get('project'):
            try:
                active_project = Project.objects.filter(pk=self.data.get('project')).first()
            except (ValueError, TypeError):
                active_project = None

        if active_project:
            from .item_delivery import project_has_scoped_inventory_lines, project_item_remaining_qty

            if project_has_scoped_inventory_lines(active_project):
                item_ids = (
                    ProjectItemLine.objects.filter(
                        project=active_project,
                        inventory_item__isnull=False,
                    )
                    .values_list('inventory_item_id', flat=True)
                    .distinct()
                )
                deliverable_ids = [
                    pk for pk in item_ids
                    if (project_item_remaining_qty(active_project, Item.objects.get(pk=pk)) or Decimal('0')) > 0
                ]
                qs = qs.filter(pk__in=deliverable_ids) if deliverable_ids else Item.objects.none()
        self.fields['item'].queryset = qs

    def clean(self):
        cleaned = super().clean()
        if self.project is None:
            self.project = cleaned.get('project')
        if not self.project:
            raise forms.ValidationError('Project is required.')

        item = cleaned.get('item')
        qty = cleaned.get('quantity')
        if self.project and item and qty is not None:
            from .item_delivery import project_item_remaining_qty, project_item_required_qty, project_item_delivered_qty

            remaining = project_item_remaining_qty(self.project, item)
            if remaining is not None and qty > remaining:
                required = project_item_required_qty(self.project, item)
                delivered = project_item_delivered_qty(self.project, item)
                if remaining <= 0:
                    raise forms.ValidationError(
                        f'All {required} unit(s) of {item.name} are already delivered to this project.'
                    )
                self.add_error(
                    'quantity',
                    f'Project requires {required} × {item.name}; {delivered} delivered. Max {remaining} more.',
                )
        cleaned['project'] = self.project
        return cleaned


class ProjectItemReturnForm(forms.Form):
    """Return delivered inventory from a project back to stock."""

    item = forms.ModelChoiceField(
        queryset=Item.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        empty_label='Select item…',
    )
    quantity = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        min_value=Decimal('1'),
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '1', 'min': '1'}),
    )
    returned_date = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
    )

    def __init__(self, *args, project=None, **kwargs):
        self.project = project
        super().__init__(*args, **kwargs)
        if project:
            from .item_delivery import project_returnable_item_ids
            ids = project_returnable_item_ids(project)
            self.fields['item'].queryset = Item.objects.filter(pk__in=ids).order_by('name')
        else:
            self.fields['item'].queryset = Item.objects.none()

    def clean(self):
        cleaned = super().clean()
        item = cleaned.get('item')
        qty = cleaned.get('quantity')
        if self.project and item and qty is not None:
            from .item_delivery import project_item_returnable_qty

            returnable = project_item_returnable_qty(self.project, item)
            if qty > returnable:
                self.add_error(
                    'quantity',
                    f'Only {returnable} unit(s) of {item.name} can be returned from this project.',
                )
            if item.track_by_serial and qty != qty.to_integral_value():
                self.add_error('quantity', 'Serial-tracked items require a whole-number quantity.')
        return cleaned

