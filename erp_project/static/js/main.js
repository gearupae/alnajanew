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
        if (href.indexOf('mailto:') === 0 || href.indexOf('tel:') === 0) {
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
        if (a.closest('.col-actions, .estimate-list-actions, .consumable-request-actions, .table-actions-inner')) {
            continue;
        }
        if (/\/\d+\/?(\?|#|$)/.test(href) && href.indexOf('_edit') === -1 && href.indexOf('/edit/') === -1) {
            if (!recordHref) {
                recordHref = href;
            }
        }
    }
    if (detailHref || recordHref) {
        return detailHref || recordHref;
    }
    const primaryCell = tr.querySelector('td.col-id a[href], td:first-child a[href]');
    if (primaryCell) {
        const primaryHref = primaryCell.getAttribute('href');
        if (primaryHref && primaryHref.indexOf('mailto:') !== 0 && primaryHref.indexOf('tel:') !== 0) {
            if (!primaryCell.closest('.col-actions, .table-actions-inner')) {
                return primaryHref;
            }
        }
    }
    const actionsCell = tr.querySelector('.col-actions, .estimate-list-actions, td:last-child');
    if (actionsCell) {
        const editLink = actionsCell.querySelector('a[href*="_edit"], a[href*="/edit/"]');
        if (editLink && !editLink.querySelector('.fa-trash, .fa-ban')) {
            return editLink.getAttribute('href');
        }
    }
    return null;
}

function erpPrepareClickableRows(table) {
    const body = table.tBodies[0];
    if (!body) {
        return;
    }
    body.querySelectorAll('tr').forEach(function (tr) {
        if (tr.querySelector('td[colspan]')) {
            tr.classList.remove('erp-clickable-row');
            return;
        }
        const href = erpResolveRowHref(tr);
        if (!href) {
            tr.classList.remove('erp-clickable-row');
            delete tr.dataset.href;
            return;
        }
        tr.classList.add('erp-clickable-row');
        tr.dataset.href = href;
    });
}

function erpRowClickIsInteractive(target) {
    if (!target || target.nodeType !== 1) {
        return false;
    }
    if (target.closest('.col-actions, .table-actions-inner, .estimate-list-actions, .consumable-request-actions')) {
        return true;
    }
    if (target.closest('.crm-inline-field-form, .estimate-status-inline')) {
        return true;
    }
    const tag = target.tagName;
    if (tag === 'A' || tag === 'BUTTON' || tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA' || tag === 'LABEL') {
        return true;
    }
    if (target.closest('a, button, .btn, .form-check, .dropdown-menu')) {
        return true;
    }
    return false;
}

function erpTableIsExcluded(table) {
    if (!table || !table.classList || !table.classList.contains('table')) {
        return true;
    }
    if (table.closest('td, #report-panel, .inline-form-container, .modal, .erp-no-list-table, [data-erp-no-list]')) {
        return true;
    }
    if (table.id && table.id.indexOf('report-') === 0) {
        return true;
    }
    if (table.dataset.erpDynamicTable === '1') {
        return true;
    }
    if (!table.querySelector('thead th')) {
        return true;
    }
    return false;
}

function erpShouldUseDataTables(table) {
    if (table.dataset.erpNoDatatable === '1') {
        return false;
    }
    if (!table.classList.contains('table-hover')) {
        return false;
    }
    if (table.querySelector('thead a.estimate-sort-link, thead .estimate-sort-th a')) {
        return false;
    }
    return true;
}

function erpWireListTable(table) {
    if (erpTableIsExcluded(table)) {
        return;
    }
    table.classList.add('erp-list-table');
    erpPrepareClickableRows(table);

    if (typeof jQuery === 'undefined' || !jQuery.fn.DataTable || !erpShouldUseDataTables(table)) {
        return;
    }
    const $table = jQuery(table);
    if (jQuery.fn.DataTable.isDataTable(table)) {
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
        drawCallback: function () {
            erpPrepareClickableRows(table);
        },
    });
}

function erpInitListTables() {
    document.querySelectorAll('main table.table').forEach(erpWireListTable);
}

function erpRefreshListTableRows(root) {
    let table = null;
    if (root && root.nodeType === 1) {
        table = root.matches && root.matches('table.table') ? root : root.closest('table');
    }
    if (table) {
        erpWireListTable(table);
        return;
    }
    document.querySelectorAll('main table.table').forEach(erpWireListTable);
}

window.erpRefreshListTableRows = erpRefreshListTableRows;

function erpInitListTableRowClicks() {
    if (document.documentElement.dataset.erpRowClickBound === '1') {
        return;
    }
    document.documentElement.dataset.erpRowClickBound = '1';
    document.addEventListener('click', function (e) {
        const main = e.target.closest('main.main-content, main');
        if (!main) {
            return;
        }
        const tr = e.target.closest('tbody tr.erp-clickable-row, tbody tr[data-href]');
        if (!tr || !main.contains(tr) || !tr.dataset.href) {
            return;
        }
        if (erpRowClickIsInteractive(e.target)) {
            return;
        }
        if (window.getSelection && String(window.getSelection()).trim().length) {
            return;
        }
        window.location.href = tr.dataset.href;
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
    document.querySelectorAll('main .customer-soa-table').forEach(function (table) {
        erpPrepareClickableRows(table);
    });
    erpInitListTableRowClicks();
    document.addEventListener('shown.bs.tab', function () {
        erpRefreshListTableRows();
    });
    window.addEventListener('pageshow', function () {
        erpRefreshListTableRows();
    });

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





