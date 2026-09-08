"""
Purchase URL configuration - Including Expense Claims and Recurring Expenses
"""
from django.urls import path
from . import views
from . import debit_note_views

app_name = 'purchase'

urlpatterns = [
    # Vendors
    path('vendors/', views.VendorListView.as_view(), name='vendor_list'),
    path('vendors/<int:pk>/edit/', views.VendorUpdateView.as_view(), name='vendor_edit'),
    path('vendors/<int:pk>/delete/', views.vendor_delete, name='vendor_delete'),
    
    # Purchase Requests
    path('requests/', views.PurchaseRequestListView.as_view(), name='pr_list'),
    path('requests/create/', views.PurchaseRequestCreateView.as_view(), name='pr_create'),
    path('requests/<int:pk>/', views.PurchaseRequestDetailView.as_view(), name='pr_detail'),
    path('requests/<int:pk>/edit/', views.PurchaseRequestUpdateView.as_view(), name='pr_edit'),
    path('requests/<int:pk>/submit/', views.pr_submit, name='pr_submit'),
    path('requests/<int:pk>/return/', views.pr_return, name='pr_return'),
    path('requests/<int:pk>/delete/', views.pr_delete, name='pr_delete'),
    path('requests/<int:pk>/approve/', views.pr_approve, name='pr_approve'),
    path('requests/<int:pk>/reject/', views.pr_reject, name='pr_reject'),
    path('requests/<int:pk>/convert/', views.pr_convert, name='pr_convert'),
    path('requests/<int:pk>/items/', views.pr_items_json, name='pr_items_json'),
    path(
        'requests/<int:pk>/vendor-attachments/upload/',
        views.pr_vendor_attachment_upload,
        name='pr_vendor_attachment_upload',
    ),
    path(
        'requests/<int:pk>/vendor-attachments/<int:attachment_id>/',
        views.pr_vendor_attachment_update,
        name='pr_vendor_attachment_update',
    ),
    path(
        'requests/<int:pk>/vendor-quotes/add/',
        views.pr_vendor_add,
        name='pr_vendor_add',
    ),
    path('requests/<int:pk>/pdf/', views.pr_pdf, name='pr_pdf'),
    
    # Purchase Orders
    path('orders/', views.PurchaseOrderListView.as_view(), name='po_list'),
    path('orders/create/', views.PurchaseOrderCreateView.as_view(), name='po_create'),
    path('orders/<int:pk>/', views.PurchaseOrderDetailView.as_view(), name='po_detail'),
    path('orders/<int:pk>/receive/', views.po_receive, name='po_receive'),
    path('orders/<int:pk>/confirm/', views.po_confirm, name='po_confirm'),
    path('orders/<int:pk>/pdf/', views.po_pdf, name='po_pdf'),
    path('orders/<int:pk>/send-email/', views.po_send_email, name='po_send_email'),
    path('orders/<int:pk>/edit/', views.PurchaseOrderUpdateView.as_view(), name='po_edit'),
    path('orders/<int:pk>/delete/', views.po_delete, name='po_delete'),
    path('orders/<int:pk>/items/', views.po_items_json, name='po_items_json'),
    
    # Vendor Bills
    path('bills/', views.VendorBillListView.as_view(), name='bill_list'),
    path('bills/create/', views.VendorBillCreateView.as_view(), name='bill_create'),
    path('bills/<int:pk>/', views.VendorBillDetailView.as_view(), name='bill_detail'),
    path('bills/<int:pk>/edit/', views.VendorBillUpdateView.as_view(), name='bill_edit'),
    path('bills/<int:pk>/delete/', views.bill_delete, name='bill_delete'),
    path('bills/<int:pk>/post/', views.bill_post, name='bill_post'),
    path('bills/<int:pk>/project/', views.bill_update_project, name='bill_update_project'),
    path('bills/<int:pk>/pay/', views.bill_make_payment, name='bill_pay'),
    path('bills/bulk-pay/prepare/', views.bill_bulk_pay_prepare, name='bill_bulk_pay_prepare'),
    path('bills/bulk-pay/', views.bill_bulk_pay, name='bill_bulk_pay'),

    # Debit Notes
    path('debit-notes/', debit_note_views.DebitNoteListView.as_view(), name='debit_note_list'),
    path('debit-notes/create/', debit_note_views.DebitNoteCreateView.as_view(), name='debit_note_create'),
    path('debit-notes/<int:pk>/', debit_note_views.DebitNoteDetailView.as_view(), name='debit_note_detail'),
    path('debit-notes/<int:pk>/edit/', debit_note_views.DebitNoteUpdateView.as_view(), name='debit_note_edit'),
    path('debit-notes/<int:pk>/approve/', debit_note_views.debit_note_approve, name='debit_note_approve'),
    path('debit-notes/<int:pk>/post/', debit_note_views.debit_note_post, name='debit_note_post'),
    path('debit-notes/<int:pk>/pdf/', debit_note_views.debit_note_pdf, name='debit_note_pdf'),
    path('bills/<int:pk>/debit-note-data/', debit_note_views.bill_debit_note_data_json, name='bill_debit_note_data_json'),
    path('bills/<int:pk>/debit-note-lines/', debit_note_views.bill_debit_note_lines_json, name='bill_debit_note_lines_json'),
    
    # Expense Claims (moved from Finance)
    path('expense-claims/', views.ExpenseClaimListView.as_view(), name='expenseclaim_list'),
    path('expense-claims/create/', views.ExpenseClaimCreateView.as_view(), name='expenseclaim_create'),
    path('expense-claims/public/submit/', views.PublicExpenseSubmitView.as_view(), name='public_expense_submit'),
    path('expense-claims/public/projects/', views.public_expense_projects, name='public_expense_projects'),
    path('expense-claims/<int:pk>/', views.ExpenseClaimDetailView.as_view(), name='expenseclaim_detail'),
    path('expense-claims/<int:pk>/submit/', views.expenseclaim_submit, name='expenseclaim_submit'),
    path('expense-claims/<int:pk>/approve/', views.expenseclaim_approve, name='expenseclaim_approve'),
    path('expense-claims/<int:pk>/reject/', views.expenseclaim_reject, name='expenseclaim_reject'),
    path('expense-claims/<int:pk>/pay/', views.expenseclaim_pay, name='expenseclaim_pay'),
    
    # Recurring Expenses (NEW)
    path('recurring-expenses/', views.RecurringExpenseListView.as_view(), name='recurringexpense_list'),
    path('recurring-expenses/create/', views.RecurringExpenseCreateView.as_view(), name='recurringexpense_create'),
    path('recurring-expenses/<int:pk>/', views.RecurringExpenseDetailView.as_view(), name='recurringexpense_detail'),
    path('recurring-expenses/<int:pk>/edit/', views.RecurringExpenseUpdateView.as_view(), name='recurringexpense_edit'),
    path('recurring-expenses/<int:pk>/delete/', views.recurringexpense_delete, name='recurringexpense_delete'),
    path('recurring-expenses/<int:pk>/execute/', views.recurringexpense_execute, name='recurringexpense_execute'),
    path('recurring-expenses/<int:pk>/pause/', views.recurringexpense_pause, name='recurringexpense_pause'),
    path('recurring-expenses/<int:pk>/resume/', views.recurringexpense_resume, name='recurringexpense_resume'),
]

