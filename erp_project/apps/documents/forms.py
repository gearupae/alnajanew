from django import forms
from django.core.exceptions import ValidationError

from .document_utils import resolve_entity
from .models import DocumentType, Document


class DocumentTypeForm(forms.ModelForm):
    class Meta:
        model = DocumentType
        fields = ['is_active', 'name', 'description', 'alert_days_before']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['is_active'].label = 'Is active'
        self.fields['is_active'].widget = forms.CheckboxInput(attrs={'class': 'form-check-input'})
        self.fields['alert_days_before'].required = False
        self.fields['alert_days_before'].help_text = (
            'Days before expiry to flag renewal. Leave blank to disable expiry alerts for this type.'
        )
        if not self.instance.pk:
            self.fields['is_active'].initial = True
        for name, field in self.fields.items():
            if name == 'is_active':
                continue
            field.widget.attrs['class'] = 'form-control'

    def clean_alert_days_before(self):
        val = self.cleaned_data.get('alert_days_before')
        if val in (None, ''):
            return None
        return val

    def clean(self):
        cleaned = super().clean()
        if self.data:
            cleaned['is_active'] = 'is_active' in self.data
        elif not self.instance.pk:
            cleaned['is_active'] = True
        return cleaned


class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = [
            'is_active',
            'document_type',
            'entity_type',
            'entity_name',
            'entity_id',
            'document_number',
            'issue_date',
            'expiry_date',
            'notes',
            'file',
        ]
        widgets = {
            'issue_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'expiry_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['is_active'].label = 'Is active'
        self.fields['is_active'].widget = forms.CheckboxInput(attrs={'class': 'form-check-input'})
        if not self.instance.pk:
            self.fields['is_active'].initial = True

        self.fields['document_type'].queryset = DocumentType.objects.filter(is_active=True).order_by('name')
        self.fields['entity_id'].required = False
        self.fields['entity_id'].label = 'Entity ID'
        self.fields['entity_id'].widget = forms.HiddenInput()
        self.fields['entity_name'].help_text = 'Pick a linked record below or enter a name manually.'
        self.fields['document_number'].label = 'Reference number'
        self.fields['document_number'].help_text = 'License / certificate / policy number for audit trail.'

        for name, field in self.fields.items():
            if name in ('is_active', 'entity_id'):
                continue
            if name in self.Meta.widgets:
                continue
            if name in ('document_type', 'entity_type'):
                field.widget.attrs['class'] = 'form-select'
            elif name == 'file':
                field.widget.attrs['class'] = 'form-control'
            else:
                field.widget.attrs['class'] = 'form-control'

    def clean(self):
        cleaned = super().clean()
        if self.data:
            cleaned['is_active'] = 'is_active' in self.data
        elif not self.instance.pk:
            cleaned['is_active'] = True

        entity_type = cleaned.get('entity_type')
        entity_id = cleaned.get('entity_id')
        entity_name = (cleaned.get('entity_name') or '').strip()

        if entity_type and entity_type not in ('other',) and entity_id:
            ok, resolved_name = resolve_entity(entity_type, entity_id)
            if not ok:
                raise ValidationError({'entity_id': 'Selected entity record was not found.'})
            if resolved_name and not entity_name:
                cleaned['entity_name'] = resolved_name

        if not (cleaned.get('document_number') or '').strip():
            raise ValidationError({'document_number': 'Reference number is required for audit trail.'})

        uploaded = cleaned.get('file')
        if not self.instance.pk and not uploaded:
            raise ValidationError({'file': 'Upload the document file.'})
        if self.instance.pk and not uploaded and not self.instance.file:
            raise ValidationError({'file': 'Upload the document file.'})

        issue = cleaned.get('issue_date')
        expiry = cleaned.get('expiry_date')
        if issue and expiry and issue > expiry:
            raise ValidationError('Issue date must be on or before expiry date.')

        return cleaned
