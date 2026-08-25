from django.urls import path
from . import views

app_name = 'documents'

urlpatterns = [
    path('', views.DocumentListView.as_view(), name='document_list'),
    path('create/', views.DocumentCreateView.as_view(), name='document_create'),
    path('types/', views.DocumentTypeListView.as_view(), name='type_list'),
    path('types/<int:pk>/edit/', views.DocumentTypeUpdateView.as_view(), name='type_edit'),
    path('types/<int:pk>/', views.DocumentTypeDetailView.as_view(), name='type_detail'),
    path('<int:pk>/edit/', views.DocumentUpdateView.as_view(), name='document_edit'),
    path('<int:pk>/delete/', views.document_delete, name='document_delete'),
    path('entity-lookup/', views.entity_lookup, name='entity_lookup'),
    path('<int:pk>/', views.DocumentDetailView.as_view(), name='document_detail'),
]





