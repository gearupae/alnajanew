"""Documents Views"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_GET
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.core.audit import log_audit
from apps.core.mixins import CreatePermissionMixin, PermissionRequiredMixin, UpdatePermissionMixin
from apps.core.utils import PermissionChecker

from .document_utils import (
    document_status_counts,
    entity_detail_url,
    filter_documents_by_status,
    lookup_entities,
)
from .forms import DocumentForm, DocumentTypeForm
from .models import Document, DocumentType


class DocumentListView(PermissionRequiredMixin, ListView):
    model = Document
    template_name = 'documents/document_list.html'
    context_object_name = 'documents'
    module_name = 'documents'
    permission_type = 'view'

    def get_queryset(self):
        queryset = Document.objects.filter(is_active=True).select_related('document_type')

        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(entity_name__icontains=search) | Q(document_number__icontains=search)
            )

        status = self.request.GET.get('status')
        queryset = filter_documents_by_status(queryset, status)
        return queryset.order_by('-created_at', '-pk')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Documents'
        all_docs = Document.objects.filter(is_active=True)
        counts = document_status_counts(all_docs)
        context['expired_count'] = counts['expired']
        context['expiring_count'] = counts['expiring']
        context['active_count'] = counts['active']
        context['can_create'] = self.request.user.is_superuser or PermissionChecker.has_permission(
            self.request.user, 'documents', 'create'
        )
        context['can_edit'] = self.request.user.is_superuser or PermissionChecker.has_permission(
            self.request.user, 'documents', 'edit'
        )
        context['can_delete'] = self.request.user.is_superuser or PermissionChecker.has_permission(
            self.request.user, 'documents', 'delete'
        )
        return context


class DocumentDetailView(PermissionRequiredMixin, DetailView):
    model = Document
    template_name = 'documents/document_detail.html'
    context_object_name = 'document'
    module_name = 'documents'
    permission_type = 'view'

    def get_queryset(self):
        return Document.objects.select_related('document_type', 'created_by', 'updated_by')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        doc = self.object
        context['title'] = doc.document_number or f'{doc.document_type.name} — {doc.entity_name}'
        context['can_edit'] = self.request.user.is_superuser or PermissionChecker.has_permission(
            self.request.user, 'documents', 'edit'
        )
        context['can_delete'] = self.request.user.is_superuser or PermissionChecker.has_permission(
            self.request.user, 'documents', 'delete'
        )
        context['entity_url'] = entity_detail_url(doc.entity_type, doc.entity_id)
        return context


class DocumentCreateView(CreatePermissionMixin, CreateView):
    model = Document
    form_class = DocumentForm
    template_name = 'documents/document_form.html'
    module_name = 'documents'

    def get_initial(self):
        initial = super().get_initial()
        for key in ('entity_type', 'entity_name'):
            val = self.request.GET.get(key)
            if val:
                initial[key] = val
        entity_id = self.request.GET.get('entity_id')
        if entity_id and str(entity_id).isdigit():
            initial['entity_id'] = int(entity_id)
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Add Document'
        context['is_edit'] = False
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        log_audit(
            self.request.user,
            'create',
            'Document',
            self.object.pk,
            {'entity': self.object.entity_name, 'type': self.object.document_type.name},
            request=self.request,
        )
        messages.success(self.request, 'Document added.')
        return response

    def get_success_url(self):
        return reverse('documents:document_detail', kwargs={'pk': self.object.pk})


class DocumentUpdateView(UpdatePermissionMixin, UpdateView):
    model = Document
    form_class = DocumentForm
    template_name = 'documents/document_form.html'
    module_name = 'documents'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Edit Document — {self.object.entity_name}'
        context['is_edit'] = True
        return context

    def form_valid(self, form):
        response = super().form_valid(form)
        log_audit(
            self.request.user,
            'update',
            'Document',
            self.object.pk,
            {'entity': self.object.entity_name, 'type': self.object.document_type.name},
            request=self.request,
        )
        messages.success(self.request, 'Document updated.')
        return response

    def get_success_url(self):
        return reverse('documents:document_detail', kwargs={'pk': self.object.pk})


class DocumentTypeListView(PermissionRequiredMixin, ListView):
    model = DocumentType
    template_name = 'documents/type_list.html'
    context_object_name = 'document_types'
    module_name = 'documents'
    permission_type = 'view'

    def get_queryset(self):
        return (
            DocumentType.objects.filter(is_active=True)
            .annotate(doc_count=Count('documents', filter=Q(documents__is_active=True)))
            .order_by('name')
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Document Types'
        context['form'] = DocumentTypeForm()
        context['can_create'] = self.request.user.is_superuser or PermissionChecker.has_permission(
            self.request.user, 'documents', 'create'
        )
        context['can_edit'] = self.request.user.is_superuser or PermissionChecker.has_permission(
            self.request.user, 'documents', 'edit'
        )
        return context

    def post(self, request, *args, **kwargs):
        form = DocumentTypeForm(request.POST)
        if form.is_valid():
            doc_type = form.save()
            messages.success(request, 'Document type created.')
            return redirect('documents:type_detail', pk=doc_type.pk)
        messages.error(request, 'Could not create document type.')
        return redirect('documents:type_list')


class DocumentTypeDetailView(PermissionRequiredMixin, DetailView):
    model = DocumentType
    template_name = 'documents/type_detail.html'
    context_object_name = 'document_type'
    module_name = 'documents'
    permission_type = 'view'

    def get_queryset(self):
        return DocumentType.objects.annotate(
            doc_count=Count('documents', filter=Q(documents__is_active=True))
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = self.object.name
        context['can_edit'] = self.request.user.is_superuser or PermissionChecker.has_permission(
            self.request.user, 'documents', 'edit'
        )
        context['type_documents'] = (
            Document.objects.filter(is_active=True, document_type=self.object)
            .select_related('document_type')
            .order_by('expiry_date', '-created_at')
        )
        return context


class DocumentTypeUpdateView(UpdatePermissionMixin, UpdateView):
    model = DocumentType
    form_class = DocumentTypeForm
    template_name = 'documents/type_form.html'
    module_name = 'documents'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Edit Document Type — {self.object.name}'
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Document type updated.')
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('documents:type_detail', kwargs={'pk': self.object.pk})


@require_GET
def entity_lookup(request):
    if not request.user.is_authenticated:
        return JsonResponse({'ok': False, 'error': 'Authentication required.'}, status=401)
    if not (
        request.user.is_superuser
        or PermissionChecker.has_permission(request.user, 'documents', 'view')
        or PermissionChecker.has_permission(request.user, 'documents', 'create')
    ):
        return JsonResponse({'ok': False, 'error': 'Permission denied.'}, status=403)

    entity_type = (request.GET.get('entity_type') or '').strip()
    if entity_type not in dict(Document.ENTITY_CHOICES):
        return JsonResponse({'ok': False, 'error': 'Invalid entity type.'}, status=400)
    results = lookup_entities(entity_type, request.GET.get('q', ''))
    return JsonResponse({'ok': True, 'results': results})


@login_required
def document_delete(request, pk):
    doc = get_object_or_404(Document, pk=pk)
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    if not (request.user.is_superuser or PermissionChecker.has_permission(request.user, 'documents', 'delete')):
        messages.error(request, 'Permission denied.')
        return redirect('documents:document_detail', pk=pk)
    doc.is_active = False
    doc.save(update_fields=['is_active', 'updated_at'])
    log_audit(
        request.user,
        'delete',
        'Document',
        doc.pk,
        {'entity': doc.entity_name, 'type': doc.document_type.name},
        request=request,
    )
    messages.success(request, 'Document deleted.')
    return redirect('documents:document_list')
