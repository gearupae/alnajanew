/**
 * Live CRM customer form validation (mirrors server rules in apps/crm/utils.py).
 */
(function (window) {
    'use strict';

    function trim(value) {
        return (value || '').trim();
    }

    function isB2bSegment(form) {
        return form.querySelector('[name="business_segment"]')?.value === 'b2b';
    }

    function validateEmail(value, required) {
        var email = trim(value);
        if (!email) {
            return required ? 'Email is required for B2B accounts.' : '';
        }
        if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
            return 'Enter a valid email address.';
        }
        return '';
    }

    function validatePhoneFormat(value, required) {
        var phone = trim(value);
        if (!phone) {
            return required ? 'Contact is required for B2B accounts.' : '';
        }
        if (!phone.startsWith('+')) {
            return 'Include country code starting with + (e.g. +971 50 741 2365).';
        }
        if (!/^[\d\s+\-().]+$/.test(phone)) {
            return 'Phone number contains invalid characters.';
        }
        var digits = phone.replace(/\D/g, '');
        if (digits.length < 10 || digits.length > 15) {
            return 'Enter a valid phone number with country code (10–15 digits, e.g. +971 50 741 2365).';
        }
        return '';
    }

    function validateWebsite(value) {
        var website = trim(value);
        if (!website) return '';
        var normalized = website;
        if (!/^https?:\/\//i.test(normalized)) {
            normalized = 'https://' + normalized;
        }
        try {
            var url = new URL(normalized);
            if (!url.hostname || !url.hostname.includes('.')) {
                return 'Enter a valid website (e.g. gear-up.ae, www.gear-up.ae, or https://gear-up.ae).';
            }
        } catch (e) {
            return 'Enter a valid website (e.g. gear-up.ae, www.gear-up.ae, or https://gear-up.ae).';
        }
        return '';
    }

    function validateCompany(value) {
        return trim(value) ? '' : 'Company name is required.';
    }

    function validateBusinessSegment(value) {
        return (value === 'b2b' || value === 'b2c') ? '' : 'Select B2B or B2C.';
    }

    function validateAssignedSalesperson(value) {
        return trim(value) ? '' : 'Select a salesman to assign this account.';
    }

    function ensureErrorEl(input) {
        var name = input.getAttribute('name') || '';
        var parent = input.parentElement;
        if (!parent) return null;
        var el = parent.querySelector('.crm-live-error[data-for="' + name + '"]');
        if (!el) {
            el = document.createElement('div');
            el.className = 'crm-live-error text-danger small';
            el.setAttribute('data-for', name);
            input.insertAdjacentElement('afterend', el);
        }
        return el;
    }

    function setFieldValidity(input, message) {
        if (!input) return !!message;
        var errEl = ensureErrorEl(input);
        if (message) {
            input.classList.add('is-invalid');
            if (errEl) {
                errEl.textContent = message;
                errEl.style.display = 'block';
            }
            input.setCustomValidity(message);
            return false;
        }
        input.classList.remove('is-invalid');
        if (errEl) {
            errEl.textContent = '';
            errEl.style.display = 'none';
        }
        input.setCustomValidity('');
        return true;
    }

    function validateField(form, input) {
        if (!input || !input.name) return true;
        var message = '';
        var b2b = isB2bSegment(form);

        switch (input.name) {
            case 'phone':
                message = validatePhoneFormat(input.value, b2b);
                break;
            case 'email':
                message = validateEmail(input.value, false);
                break;
            case 'website':
                message = validateWebsite(input.value);
                break;
            case 'company':
                message = validateCompany(input.value);
                break;
            case 'business_segment':
                message = validateBusinessSegment(input.value);
                break;
            case 'assigned_salesperson':
                message = validateAssignedSalesperson(input.value);
                break;
            default:
                return true;
        }
        return setFieldValidity(input, message);
    }

    function applyB2bRequirements(form) {
        if (!isB2bSegment(form)) {
            ['phone'].forEach(function (name) {
                var input = form.querySelector('[name="' + name + '"]');
                if (input) setFieldValidity(input, '');
            });
            return true;
        }
        var ok = true;
        var checks = [
            ['phone', 'Contact is required for B2B accounts.'],
        ];
        checks.forEach(function (pair) {
            var input = form.querySelector('[name="' + pair[0] + '"]');
            if (input && !trim(input.value)) {
                setFieldValidity(input, pair[1]);
                ok = false;
            }
        });
        return ok;
    }

    function validateForm(form) {
        var ok = true;
        var names = ['company', 'business_segment', 'assigned_salesperson', 'email', 'phone', 'website'];
        names.forEach(function (name) {
            var input = form.querySelector('[name="' + name + '"]');
            if (input && !validateField(form, input)) {
                ok = false;
            }
        });
        if (!applyB2bRequirements(form)) {
            ok = false;
        }
        if (!form.checkValidity()) {
            ok = false;
        }
        return ok;
    }

    function attachForm(form) {
        if (!form || form.dataset.crmValidationAttached === '1') return;
        form.dataset.crmValidationAttached = '1';

        var liveFields = ['phone', 'email', 'website', 'company', 'business_segment', 'assigned_salesperson'];
        liveFields.forEach(function (name) {
            var input = form.querySelector('[name="' + name + '"]');
            if (!input) return;
            input.addEventListener('input', function () {
                validateField(form, input);
            });
            input.addEventListener('blur', function () {
                validateField(form, input);
            });
        });

        var typeSel = form.querySelector('[name="customer_type"]');
        var segSel = form.querySelector('[name="business_segment"]');
        function revalidateB2bFields() {
            ['phone'].forEach(function (name) {
                var input = form.querySelector('[name="' + name + '"]');
                if (input) validateField(form, input);
            });
            applyB2bRequirements(form);
        }
        if (typeSel) typeSel.addEventListener('change', revalidateB2bFields);
        if (segSel) segSel.addEventListener('change', revalidateB2bFields);

        form.addEventListener('submit', function (e) {
            if (!validateForm(form)) {
                e.preventDefault();
                e.stopPropagation();
                var firstInvalid = form.querySelector('.is-invalid');
                if (firstInvalid) {
                    firstInvalid.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    firstInvalid.focus({ preventScroll: true });
                }
            }
        });
    }

    function init() {
        document.querySelectorAll('form[data-crm-customer-form]').forEach(attachForm);
    }

    window.CrmCustomerValidation = {
        attachForm: attachForm,
        validateForm: validateForm,
        validateField: validateField,
        validatePhoneFormat: validatePhoneFormat,
        validateEmail: validateEmail,
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})(window);
