/**
 * Searchable Select2 for CRM assigned salesman fields.
 */
(function (window) {
    'use strict';

    function initCrmSalespersonSelect2(root) {
        if (typeof $ === 'undefined' || !$.fn.select2) return;
        var scope = root || document;
        $(scope).find('.select2-crm-salesperson').each(function () {
            var el = this;
            if (el.disabled) return;
            var $el = $(el);
            if ($el.data('select2')) return;
            var placeholder = el.getAttribute('data-placeholder')
                || (el.querySelector('option[value=""]') && el.querySelector('option[value=""]').textContent.trim())
                || 'Search by name or employee code…';
            $el.select2({
                theme: 'bootstrap-5',
                width: '100%',
                dropdownParent: $(document.body),
                allowClear: !el.required,
                minimumResultsForSearch: 0,
                dropdownCssClass: 'crm-salesperson-select2-dropdown',
                placeholder: placeholder,
            });
        });
    }

    window.initCrmSalespersonSelect2 = initCrmSalespersonSelect2;

    function onReady() {
        initCrmSalespersonSelect2(document);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', onReady);
    } else {
        onReady();
    }
})(window);
