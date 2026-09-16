/**
 * Show/hide B2B-only CRM customer fields (TRN, documents, website layout).
 */
(function (window) {
    'use strict';

    function rootFor(el) {
        return el.closest('[data-crm-compact-form]') || el.closest('form') || document;
    }

    function toggleCompactCustomerFields(container) {
        if (!container) return;
        var seg = container.querySelector('[name="business_segment"]');
        var isB2b = seg && seg.value === 'b2b';
        var trnInput = container.querySelector('[name="trn"]');
        var websiteWrap = container.querySelector('#crmWebsiteFieldWrap');

        container.querySelectorAll('.crm-b2b-only-field').forEach(function (el) {
            el.style.display = isB2b ? '' : 'none';
        });

        if (trnInput && !isB2b) {
            trnInput.value = '';
        }

        if (websiteWrap) {
            websiteWrap.classList.toggle('col-md-6', !isB2b);
            websiteWrap.classList.toggle('col-md-3', isB2b);
        }

        var emailInput = container.querySelector('[name="email"]');
        var phoneInput = container.querySelector('[name="phone"]');
        if (emailInput) emailInput.required = isB2b;
        if (phoneInput) phoneInput.required = isB2b;

        container.querySelectorAll('.crm-b2b-required-star').forEach(function (el) {
            el.style.display = isB2b ? '' : 'none';
        });
    }

    function attach(container) {
        if (!container || container.dataset.crmToggleAttached === '1') return;
        container.dataset.crmToggleAttached = '1';
        var seg = container.querySelector('[name="business_segment"]');
        if (seg) {
            seg.addEventListener('change', function () {
                toggleCompactCustomerFields(rootFor(seg));
            });
        }
        toggleCompactCustomerFields(container);
    }

    function init() {
        document.querySelectorAll('[data-crm-compact-form]').forEach(attach);
    }

    window.CrmCustomerFormToggle = {
        attach: attach,
        toggle: toggleCompactCustomerFields,
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})(window);
