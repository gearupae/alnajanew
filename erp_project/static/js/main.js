/* Safety Point ERP - Main JavaScript */

// Global AJAX Setup
$.ajaxSetup({
    beforeSend: function(xhr, settings) {
        if (!/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type) && !this.crossDomain) {
            xhr.setRequestHeader("X-CSRFToken", getCookie('csrftoken'));
        }
    }
});

// Get CSRF Token
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Toggle Inline Form
function toggleInlineForm(formId) {
    const form = document.getElementById(formId);
    if (form) {
        form.classList.toggle('show');
        if (form.classList.contains('show')) {
            form.scrollIntoView({ behavior: 'smooth', block: 'start' });
            const firstInput = form.querySelector('input:not([type="hidden"]), select, textarea');
            if (firstInput) {
                setTimeout(() => firstInput.focus(), 300);
            }
            if (formId === 'customerForm' && window.CrmCustomerFormToggle) {
                const compact = form.querySelector('[data-crm-compact-form]');
                if (compact) {
                    window.CrmCustomerFormToggle.attach(compact);
                }
            }
            if (formId === 'customerForm' && window.crmInitAssignedSalespersonSelect2) {
                setTimeout(function () {
                    window.crmInitAssignedSalespersonSelect2();
                }, 60);
            }
        }
    }
}

// Cancel Inline Form
function cancelInlineForm(formId) {
    const form = document.getElementById(formId);
    if (form) {
        form.classList.remove('show');
        const formElement = form.querySelector('form');
        if (formElement) {
            if (formId === 'customerForm' && window.crmDestroyAssignedSalespersonSelect2) {
                window.crmDestroyAssignedSalespersonSelect2();
            }
            if (formId === 'accountForm') {
                form.querySelectorAll('.account-parent-query').forEach(function (el) {
                    el.value = '';
                });
            }
            formElement.reset();
            if (formId === 'customerForm' && window.CrmCustomerFormToggle) {
                const compact = form.querySelector('[data-crm-compact-form]');
                if (compact) {
                    window.CrmCustomerFormToggle.toggle(compact);
                }
            }
        }
    }
}

// Confirmation Dialog
function confirmAction(message, callback) {
    if (confirm(message)) {
        callback();
    }
}

// Delete Confirmation
function confirmDelete(url, itemName) {
    if (confirm(`Are you sure you want to delete "${itemName}"? This action cannot be undone.`)) {
        window.location.href = url;
    }
}

// Format Currency
function formatCurrency(amount, currency = 'AED') {
    return new Intl.NumberFormat('en-AE', {
        style: 'currency',
        currency: currency
    }).format(amount);
}

// Format Date
function formatDate(dateStr, format = 'short') {
    const date = new Date(dateStr);
    const options = format === 'short' 
        ? { day: '2-digit', month: '2-digit', year: 'numeric' }
        : { day: '2-digit', month: 'long', year: 'numeric' };
    return date.toLocaleDateString('en-GB', options);
}

// Show Toast Notification
function showToast(type, message) {
    toastr[type](message);
}

// Loading State
function showLoading() {
    $('body').append('<div class="loading-overlay"><div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading...</span></div></div>');
}

function hideLoading() {
    $('.loading-overlay').remove();
}

// Form Validation
function validateForm(formId) {
    const form = document.getElementById(formId);
    if (!form) return true;
    
    let isValid = true;
    const requiredFields = form.querySelectorAll('[required]');
    
    requiredFields.forEach(field => {
        if (!field.value.trim()) {
            field.classList.add('is-invalid');
            isValid = false;
        } else {
            field.classList.remove('is-invalid');
        }
    });
    
    return isValid;
}

function erpResolveRowHref(tr) {
    if (tr.dataset.href) {
        return tr.dataset.href;
    }
    if (tr.dataset.projectUrl) {
        return tr.dataset.projectUrl;
    }
    if (tr.dataset.rowHref) {
        return tr.dataset.rowHref;
    }
    let detailHref = null;
    let recordHref = null;
    const links = tr.querySelectorAll('a[href]');
    for (let i = 0; i < links.length; i++) {
        const a = links[i];
        const href = a.getAttribute('href');
        if (!href || href === '#' || href.indexOf('javascript:') === 0) {
            continue;
        }
        if (a.querySelector('.fa-edit, .fa-trash, .fa-pdf, .fa-file-pdf, .fa-download')) {
            continue;
        }
        if (a.target === '_blank' || a.hasAttribute('download')) {
            continue;
        }
        if (href.indexOf('_detail') !== -1 || href.indexOf('/detail/') !== -1) {
            detailHref = href;
            break;
        }
        if (/\/\d+\/?(\?|#|$)/.test(href) && (href.indexOf('_edit') === -1 && href.indexOf('/edit') === -1)) {
            if (!recordHref) {
                recordHref = href;
            }
        }
    }
    return detailHref || recordHref || null;
}

function erpPrepareClickableRows(table) {
    const body = table.tBodies[0];
    if (!body) {
        return;
    }
    body.querySelectorAll('tr').forEach(function (tr) {
        if (tr.querySelector('td[colspan]')) {
            return;
        }
        const href = erpResolveRowHref(tr);
        if (!href) {
            return;
        }
        tr.classList.add('erp-clickable-row');
        tr.dataset.href = href;
    });
}

function erpInitListTables() {
    if (typeof jQuery === 'undefined') {
        return;
    }
    const $ = jQuery;
    $('main .card .table-responsive table.table-hover, main .table-responsive table.table-hover').each(function () {
        const table = this;
        const $table = $(table);
        if ($table.closest('td, #report-panel, .inline-form-container, .modal, .erp-no-list-table, [data-erp-no-list]').length) {
            return;
        }
        if (table.id && table.id.indexOf('report-') === 0) {
            return;
        }
        if (table.dataset.erpDynamicTable === '1') {
            return;
        }
        if (!table.querySelector('thead')) {
            return;
        }
        if (!table.querySelector('thead th')) {
            return;
        }
        $table.addClass('erp-list-table');

        erpPrepareClickableRows(table);

        if (!$.fn.DataTable || $.fn.DataTable.isDataTable(table)) {
            return;
        }

        const nonSortable = [];
        table.querySelectorAll('thead th').forEach(function (th, i) {
            const label = (th.textContent || '').trim().toLowerCase();
            if (th.classList.contains('col-actions') || label === 'actions' || label === 'action') {
                nonSortable.push(i);
            }
        });

        const rowCount = $table.find('tbody tr').filter(function () {
            return !this.querySelector('td[colspan]');
        }).length;
        const $card = $table.closest('.card');
        const djangoPaginated = $card.find('.pagination').length > 0;

        $table.DataTable({
            paging: !djangoPaginated && rowCount > 50,
            pageLength: 25,
            order: [],
            ordering: true,
            searching: false,
            lengthChange: false,
            info: rowCount > 25,
            autoWidth: false,
            columnDefs: nonSortable.length ? [{ orderable: false, targets: nonSortable }] : [],
        });
    });
}

function erpInitListTableRowClicks() {
    document.querySelectorAll('table.erp-list-table tbody').forEach(function (tbody) {
        if (tbody.dataset.erpRowClickBound === '1') {
            return;
        }
        tbody.dataset.erpRowClickBound = '1';
        tbody.addEventListener('click', function (e) {
            const tr = e.target.closest('tr.erp-clickable-row');
            if (!tr || !tr.dataset.href) {
                return;
            }
            if (e.target.closest('a, button, input, select, textarea, label, form, .btn, .form-check, .dropdown-menu')) {
                return;
            }
            window.location.href = tr.dataset.href;
        });
    });
}

// Clear Form Validation
function clearValidation(formId) {
    const form = document.getElementById(formId);
    if (!form) return;
    
    const fields = form.querySelectorAll('.is-invalid');
    fields.forEach(field => field.classList.remove('is-invalid'));
}

// Initialize Components
document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Initialize popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function(popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
    
    // Auto-hide alerts
    setTimeout(function() {
        const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
        alerts.forEach(function(alert) {
            new bootstrap.Alert(alert).close();
        });
    }, 5000);
    
    erpInitListTables();
    erpInitListTableRowClicks();

    // Mobile sidebar toggle
    document.getElementById('sidebarToggle')?.addEventListener('click', function() {
        document.querySelector('.sidebar').classList.toggle('show');
    });
    
    // Close sidebar on mobile when clicking outside
    document.addEventListener('click', function(e) {
        const sidebar = document.querySelector('.sidebar');
        const sidebarToggle = document.getElementById('sidebarToggle');
        if (!sidebar) return;

        if (window.innerWidth < 992 && 
            sidebar.classList.contains('show') && 
            !sidebar.contains(e.target) && 
            e.target !== sidebarToggle) {
            sidebar.classList.remove('show');
        }
    });
});

// Export functions for global use
window.toggleInlineForm = toggleInlineForm;
window.cancelInlineForm = cancelInlineForm;
window.confirmAction = confirmAction;
window.confirmDelete = confirmDelete;
window.formatCurrency = formatCurrency;
window.formatDate = formatDate;
window.showToast = showToast;
window.showLoading = showLoading;
window.hideLoading = hideLoading;
window.validateForm = validateForm;
window.clearValidation = clearValidation;





