/**
 * Prefill CRM customer forms when phone, email, or TRN matches a saved record.
 */
(function (window) {
    'use strict';

    var LOOKUP_FIELDS = ['phone', 'email', 'trn'];
    var DEBOUNCE_MS = 500;

    function trim(value) {
        return (value || '').trim();
    }

    function phoneDigits(value) {
        return trim(value).replace(/\D/g, '');
    }

    function buildLookupQuery(fieldName, value) {
        value = trim(value);
        if (!value) {
            return null;
        }

        if (fieldName === 'phone') {
            if (/^CUST-/i.test(value)) {
                return { customer_number: value };
            }
            if (phoneDigits(value).length >= 10) {
                return { phone: value };
            }
            return null;
        }

        if (fieldName === 'email') {
            if (value.indexOf('@') > 0 && value.indexOf('.') > value.indexOf('@')) {
                return { email: value };
            }
            return null;
        }

        if (fieldName === 'trn') {
            if (value.length >= 3) {
                return { trn: value };
            }
            return null;
        }

        return null;
    }

    function setFieldValue(form, name, value) {
        var el = form.querySelector('[name="' + name + '"]');
        if (!el) {
            return;
        }

        if (el.type === 'checkbox') {
            el.checked = !!value;
            return;
        }

        if (el.tagName === 'SELECT' && el.multiple) {
            var vals = Array.isArray(value) ? value : [];
            Array.prototype.forEach.call(el.options, function (opt) {
                opt.selected = vals.indexOf(opt.value) >= 0;
            });
            if (typeof window.$ !== 'undefined' && window.$(el).data('select2')) {
                window.$(el).val(vals).trigger('change');
            }
            return;
        }

        if (el.tagName === 'SELECT') {
            el.value = value == null ? '' : String(value);
            if (typeof window.$ !== 'undefined' && window.$(el).data('select2')) {
                window.$(el).val(el.value || null).trigger('change');
            }
            el.dispatchEvent(new Event('change', { bubbles: true }));
            return;
        }

        el.value = value == null ? '' : String(value);
    }

    function applyCustomerData(form, data) {
        var fields = [
            'name', 'company', 'email', 'phone', 'address', 'city', 'country',
            'trn', 'trade_license_number', 'website', 'scope', 'job_type',
            'primary_project', 'payment_terms', 'credit_limit', 'status',
            'customer_type', 'lead_kanban_stage', 'assigned_salesperson',
            'business_segment', 'notes',
        ];

        fields.forEach(function (name) {
            if (Object.prototype.hasOwnProperty.call(data, name)) {
                setFieldValue(form, name, data[name]);
            }
        });

        if (Object.prototype.hasOwnProperty.call(data, 'is_active')) {
            setFieldValue(form, 'is_active', data.is_active ? 'on' : '');
        }

        form.dispatchEvent(new CustomEvent('crm-customer-prefilled', {
            bubbles: true,
            detail: { customer: data },
        }));
    }

    function ensureBanner(form) {
        var banner = form.querySelector('.crm-lookup-banner');
        if (!banner) {
            banner = document.createElement('div');
            banner.className = 'alert alert-info py-2 px-3 mb-3 crm-lookup-banner';
            form.insertBefore(banner, form.firstChild);
        }
        return banner;
    }

    function hideBanner(form) {
        var banner = form.querySelector('.crm-lookup-banner');
        if (banner) {
            banner.remove();
        }
    }

    function showBanner(form, data) {
        var banner = ensureBanner(form);
        var label = data.company || data.name || data.customer_number;
        var link = data.detail_url
            ? '<a href="' + data.detail_url + '" class="alert-link fw-semibold" target="_blank" rel="noopener">' +
                data.customer_number + '</a>'
            : data.customer_number;
        banner.innerHTML =
            '<i class="fas fa-search me-2"></i>' +
            'Loaded saved details from ' + link + (label ? ' (' + label + ')' : '') + '. ' +
            'Review and save as a new record or update as needed.';
    }

    function attachForm(form) {
        if (!form || form.dataset.crmLookupAttached === '1') {
            return;
        }

        var lookupUrl = form.dataset.crmLookupUrl;
        if (!lookupUrl) {
            return;
        }

        form.dataset.crmLookupAttached = '1';

        var excludePk = form.dataset.crmExcludePk || '';
        var lastLookupKey = '';
        var debounceTimer = null;
        var activeRequest = null;

        function runLookup(fieldName, value) {
            var query = buildLookupQuery(fieldName, value);
            if (!query) {
                lastLookupKey = '';
                hideBanner(form);
                return;
            }

            var lookupKey = fieldName + ':' + JSON.stringify(query);
            if (lookupKey === lastLookupKey) {
                return;
            }

            if (activeRequest) {
                activeRequest.abort();
            }

            var params = new URLSearchParams(query);
            if (excludePk) {
                params.set('exclude_pk', excludePk);
            }

            activeRequest = new AbortController();

            fetch(lookupUrl + '?' + params.toString(), {
                credentials: 'same-origin',
                headers: { 'Accept': 'application/json' },
                signal: activeRequest.signal,
            })
                .then(function (response) {
                    return response.json();
                })
                .then(function (payload) {
                    activeRequest = null;
                    if (!payload || !payload.ok) {
                        return;
                    }
                    if (!payload.found || !payload.customer) {
                        lastLookupKey = '';
                        hideBanner(form);
                        return;
                    }

                    lastLookupKey = lookupKey;
                    applyCustomerData(form, payload.customer);
                    showBanner(form, payload.customer);
                })
                .catch(function (err) {
                    if (err && err.name === 'AbortError') {
                        return;
                    }
                    activeRequest = null;
                });
        }

        function scheduleLookup(fieldName, value) {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(function () {
                runLookup(fieldName, value);
            }, DEBOUNCE_MS);
        }

        LOOKUP_FIELDS.forEach(function (fieldName) {
            var input = form.querySelector('[name="' + fieldName + '"]');
            if (!input) {
                return;
            }

            input.addEventListener('input', function () {
                scheduleLookup(fieldName, input.value);
            });
            input.addEventListener('blur', function () {
                clearTimeout(debounceTimer);
                runLookup(fieldName, input.value);
            });
        });
    }

    function init() {
        document.querySelectorAll('form[data-crm-lookup-url]').forEach(attachForm);
    }

    window.CrmCustomerLookup = {
        attachForm: attachForm,
        applyCustomerData: applyCustomerData,
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})(window);
