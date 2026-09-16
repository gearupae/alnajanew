"""
Property Management URLs - PDC & Bank Reconciliation
"""
from django.urls import path
from . import views

app_name = 'property'

urlpatterns = [
    # Properties
    path('properties/', views.PropertyListView.as_view(), name='property_list'),
    path('properties/create/', views.PropertyCreateView.as_view(), name='property_create'),
    path('properties/<int:pk>/', views.PropertyDetailView.as_view(), name='property_detail'),
    path('properties/<int:pk>/edit/', views.PropertyUpdateView.as_view(), name='property_update'),
    path('properties/<int:property_id>/units/create/', views.UnitCreateView.as_view(), name='unit_create'),
    path('units/<int:pk>/edit/', views.UnitUpdateView.as_view(), name='unit_update'),
    path('units/<int:pk>/', views.UnitDetailView.as_view(), name='unit_detail'),
    
    # Tenants
    path('tenants/', views.TenantListView.as_view(), name='tenant_list'),
    path('tenants/create/', views.TenantCreateView.as_view(), name='tenant_create'),
    path('tenants/<int:pk>/', views.TenantDetailView.as_view(), name='tenant_detail'),
    path('tenants/<int:pk>/edit/', views.TenantUpdateView.as_view(), name='tenant_update'),
    
    # Leases
    path('leases/', views.LeaseListView.as_view(), name='lease_list'),
    path('leases/create/', views.LeaseCreateView.as_view(), name='lease_create'),
    path('leases/<int:pk>/', views.LeaseDetailView.as_view(), name='lease_detail'),
    path('leases/<int:pk>/edit/', views.LeaseUpdateView.as_view(), name='lease_update'),
    path('leases/<int:lease_id>/rent-invoices/create/', views.rent_invoice_create, name='rent_invoice_create'),
    path('leases/<int:lease_id>/rent-invoices/generate/', views.generate_lease_rent_invoices, name='generate_lease_rent_invoices'),
    path('leases/<int:lease_id>/security-deposit/create/', views.security_deposit_create, name='security_deposit_create'),
    
    # Rent invoices & security deposits
    path('rent-invoices/create/', views.rent_invoice_create, name='rent_invoice_create_standalone'),
    path('rent-invoices/<int:pk>/', views.RentInvoiceDetailView.as_view(), name='rent_invoice_detail'),
    path('rent-invoices/<int:pk>/post/', views.rent_invoice_post, name='rent_invoice_post'),
    path('security-deposits/<int:pk>/receive/', views.security_deposit_receive, name='security_deposit_receive'),
    path('security-deposits/<int:pk>/refund/', views.security_deposit_refund, name='security_deposit_refund'),
    
    # PDC Cheques
    path('pdc/', views.PDCListView.as_view(), name='pdc_list'),
    path('pdc/create/', views.PDCCreateView.as_view(), name='pdc_create'),
    path('pdc/<int:pk>/', views.PDCDetailView.as_view(), name='pdc_detail'),
    path('pdc/<int:pk>/deposit/', views.pdc_deposit, name='pdc_deposit'),
    path('pdc/<int:pk>/clear/', views.pdc_clear, name='pdc_clear'),
    path('pdc/<int:pk>/bounce/', views.pdc_bounce, name='pdc_bounce'),
    
    # Bank Reconciliation with PDC
    path('reconciliation/', views.pdc_bank_reconciliation, name='pdc_bank_reconciliation'),
    path('reconciliation/auto-match/<int:statement_id>/', views.pdc_auto_match, name='pdc_auto_match'),
    path('reconciliation/allocate/<int:line_id>/', views.pdc_manual_allocation, name='pdc_manual_allocation'),
    
    # Reports
    path('reports/pdc-register/', views.pdc_register_report, name='pdc_register_report'),
    path('reports/pdc-outstanding/', views.pdc_outstanding_report, name='pdc_outstanding_report'),
    path('reports/reconciliation-exceptions/', views.bank_reconciliation_exceptions_report, name='reconciliation_exceptions_report'),
    path('reports/ambiguous-matches/', views.ambiguous_match_log_report, name='ambiguous_match_log_report'),
    path('reports/tenant-ledger/<int:tenant_id>/', views.tenant_ledger_report, name='tenant_ledger_report'),
    
    # API
    path('api/pdc/search/', views.api_pdc_search, name='api_pdc_search'),
    path('api/pdc/validate-uniqueness/', views.api_validate_pdc_uniqueness, name='api_validate_pdc_uniqueness'),
]

