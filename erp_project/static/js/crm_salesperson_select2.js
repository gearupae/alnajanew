/**
 * Searchable Select2 for CRM assigned salesman fields.
 */
(function (window) {
    'use strict';

    function readSalesmanOptions() {
        var node = document.getElementById('crm-salesman-options');
        if (!node) {
            return [];
        }
        try {
            return JSON.parse(node.textContent) || [];
        } catch (err) {
            return [];
        }
    }

    function destroySelect2($el) {
        if ($el && $el.data('select2')) {
            $el.select2('destroy');
        }
    }

    function countNativeOptions(el) {
        return el.querySelectorAll('option[value]:not([value=""])').length;
    }

    function applySelect2(el, options) {
        var $el = $(el);
        destroySelect2($el);
        $el.select2(Object.assign({
            theme: 'bootstrap-5',
            width: '100%',
            dropdownParent: $(document.body),
            minimumResultsForSearch: 0,
            dropdownCssClass: 'crm-salesperson-select2-dropdown',
        }, options));
    }

    function initFilterSalespersonSelect2(el) {
        if (!el || el.disabled || typeof $ === 'undefined' || !$.fn.select2) {
            return;
        }
        var placeholder = el.getAttribute('data-placeholder')
            || (el.querySelector('option[value=""]') && el.querySelector('option[value=""]').textContent.trim())
            || 'Search by name or employee code…';
        applySelect2(el, {
            allowClear: true,
            placeholder: placeholder,
        });
    }

    function initCustomerFormSalespersonSelect2(container) {
        var root = container || document;
        var el = root.querySelector ? root.querySelector('#id_assigned_salesperson') : null;
        if (!el || el.disabled || typeof $ === 'undefined' || !$.fn.select2) {
            return;
        }
        if ($(el).data('select2')) {
            return;
        }

        var selected = el.value || el.getAttribute('data-default-salesperson') || '';
        var $el = $(el);

        if (countNativeOptions(el) > 0) {
            applySelect2(el, {
                allowClear: false,
                placeholder: el.getAttribute('data-placeholder') || 'Search by name or employee code…',
            });
        } else {
            var rows = readSalesmanOptions().map(function (row) {
                return { id: String(row.id), text: row.label };
            });
            if (!rows.length) {
                return;
            }
            $el.empty();
            applySelect2(el, {
                allowClear: false,
                placeholder: 'Search by name or employee code…',
                data: [{ id: '', text: '— Select salesman —' }].concat(rows),
            });
        }

        if (selected) {
            $el.val(String(selected)).trigger('change.select2');
        }
    }

    function initCrmSalespersonFilterSelect2(root) {
        var scope = root || document;
        $(scope).find('.select2-crm-filter-salesman').each(function () {
            initFilterSalespersonSelect2(this);
        });
    }

    function destroyCrmSalespersonSelect2(root) {
        if (typeof $ === 'undefined' || !$.fn.select2) {
            return;
        }
        var scope = root || document;
        $(scope).find('#id_assigned_salesperson').each(function () {
            destroySelect2($(this));
        });
    }

    function bootCustomerFormSalesmanSelect2() {
        var form = document.getElementById('customerForm');
        if (!form || !form.classList.contains('show')) {
            return;
        }
        initCustomerFormSalespersonSelect2(form);
    }

    window.initCrmCustomerFormSalespersonSelect2 = initCustomerFormSalespersonSelect2;
    window.destroyCrmSalespersonSelect2 = destroyCrmSalespersonSelect2;
    window.initCrmSalespersonFilterSelect2 = initCrmSalespersonFilterSelect2;

    function onReady() {
        initCrmSalespersonFilterSelect2(document);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', onReady);
    } else {
        onReady();
    }

    document.addEventListener('click', function (event) {
        var target = event.target;
        if (!target || !target.closest) {
            return;
        }
        if (target.closest('[onclick*="toggleInlineForm(\'customerForm\')"]')
            || target.closest('#customerForm')) {
            setTimeout(bootCustomerFormSalesmanSelect2, 60);
        }
    }, true);

    document.addEventListener('focusin', function (event) {
        var el = event.target;
        if (!el || el.id !== 'id_assigned_salesperson') {
            return;
        }
        bootCustomerFormSalesmanSelect2();
    });
})(window);
