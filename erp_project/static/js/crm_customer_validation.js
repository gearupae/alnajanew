/**
 * Live CRM customer form validation (mirrors server rules in apps/crm/utils.py).
 */
(function (window) {
    'use strict';

    function trim(value) {
        return (value || '').trim();
    }

    function isCustomerType(form) {
        var hidden = form.querySelector('input[name="customer_type"][type="hidden"]');
        if (hidden) return hidden.value === 'customer';
        var sel = form.querySelector('[name="customer_type"]');
        return sel ? sel.value === 'customer' : false;
    }

    function validatePhoneFormat(value) {
        var phone = trim(value);
        if (!phone) {
            return '';
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

    function validateEmail(value) {
        var email = trim(value);
        if (!email) {
            return '';
        }
        if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
            return 'Enter a valid email address.';
        }
        return '';
    }

    function validateCustomerContact(form) {
        if (!isCustomerType(form)) {
            return '';
        }
        var email = trim(form.querySelector('[name="email"]')?.value);
        var phone = trim(form.querySelector('[name="phone"]')?.value);
        if (!email && !phone) {
            return 'Enter an email or phone number for customers.';
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

        switch (input.name) {
            case 'phone':
                message = validatePhoneFormat(input.value);
                break;
            case 'email':
                message = validateEmail(input.value);
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

    function applyCustomerContactRequirement(form) {
        var message = validateCustomerContact(form);
        if (!message) {
            return true;
        }
        var emailInput = form.querySelector('[name="email"]');
        var phoneInput = form.querySelector('[name="phone"]');
        var ok = true;
        if (emailInput && !trim(emailInput.value)) {
            setFieldValidity(emailInput, message);
            ok = false;
        }
        if (phoneInput && !trim(phoneInput.value)) {
            setFieldValidity(phoneInput, message);
            ok = false;
        }
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
        if (!applyCustomerContactRequirement(form)) {
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
        var typeHidden = form.querySelector('input[name="customer_type"][type="hidden"]');
        function revalidateContactFields() {
            ['email', 'phone'].forEach(function (name) {
                var input = form.querySelector('[name="' + name + '"]');
                if (input) validateField(form, input);
            });
            applyCustomerContactRequirement(form);
        }
        if (typeSel) typeSel.addEventListener('change', revalidateContactFields);
        if (typeHidden) {
            /* fixed customer type — no listener needed */
        }

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
