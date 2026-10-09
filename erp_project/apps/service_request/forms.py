"""
Service Request forms.
"""
from django import forms
from .models import ServiceRequest, ServiceRequestItem, ServiceRequestAttachment


class ServiceRequestForm(forms.ModelForm):
    """Form for creating/editing service requests."""
    
    class Meta:
        model = ServiceRequest
        fields = ['date', 'required_by_date', 'department', 'priority', 'status', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d'),
            'required_by_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}, format='%Y-%m-%d'),
            'department': forms.Select(attrs={'class': 'form-select sr-department-select'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.hr.models import Department
        self.fields['department'].queryset = Department.objects.filter(is_active=True)
        self.fields['required_by_date'].required = False
        self.fields['notes'].required = False


class ServiceRequestItemForm(forms.ModelForm):
    class Meta:
        model = ServiceRequestItem
        fields = ['inventory_item', 'service_description', 'vendor', 'quantity', 'unit', 'estimated_unit_cost']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.inventory.models import Item
        from apps.purchase.models import Vendor
        if self.is_bound:
            self.fields['inventory_item'].queryset = Item.usable()
        elif self.instance.pk and self.instance.inventory_item_id:
            self.fields['inventory_item'].queryset = Item.usable().filter(
                pk=self.instance.inventory_item_id
            )
        else:
            self.fields['inventory_item'].queryset = Item.usable().none()
        self.fields['inventory_item'].required = False
        self.fields['inventory_item'].widget.attrs.update({
            'class': 'form-select item-inventory-select',
        })
        self.fields['service_description'].required = False
        self.fields['service_description'].widget = forms.TextInput(attrs={
            'class': 'form-control form-control-sm item-description-input',
            'placeholder': 'Optional description…',
        })
        if self.is_bound:
            self.fields['vendor'].queryset = Vendor.objects.filter(is_active=True, status='active')
        elif self.instance.pk and self.instance.vendor_id:
            self.fields['vendor'].queryset = Vendor.objects.filter(
                pk=self.instance.vendor_id,
                is_active=True,
                status='active',
            )
        else:
            self.fields['vendor'].queryset = Vendor.objects.none()
        self.fields['vendor'].widget.attrs['class'] = 'form-select sr-vendor-select'
        self.fields['vendor'].required = False
        for field_name, field in self.fields.items():
            if field_name not in ('vendor', 'inventory_item'):
                field.widget.attrs['class'] = 'form-control'

    def clean(self):
        cleaned = super().clean()
        if self.cleaned_data.get('DELETE'):
            return cleaned
        item = cleaned.get('inventory_item')
        description = (cleaned.get('service_description') or '').strip()
        cleaned['service_description'] = description
        if not item and not description:
            raise forms.ValidationError('Select an item or enter a description.')
        return cleaned


ServiceRequestItemFormSet = forms.inlineformset_factory(
    ServiceRequest,
    ServiceRequestItem,
    form=ServiceRequestItemForm,
    extra=1,
    can_delete=True
)


class ServiceRequestAttachmentForm(forms.ModelForm):
    class Meta:
        model = ServiceRequestAttachment
        fields = ['file']
        widgets = {
            'file': forms.FileInput(attrs={'class': 'form-control'}),
        }


class ServiceRequestRejectForm(forms.Form):
    """Form for reject/return with comments."""
    comment = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Enter comment/reason...'}),
        label='Comment'
    )
