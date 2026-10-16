(function () {
    function parseParentOptions() {
        var el = document.getElementById('finance-account-parent-options');
        if (!el) {
            return [];
        }
        try {
            return JSON.parse(el.textContent);
        } catch (e) {
            return [];
        }
    }

    function destroyPicker(picker) {
        if (picker._outsideHandler) {
            document.removeEventListener('click', picker._outsideHandler);
            picker._outsideHandler = null;
        }
        var menu = picker.querySelector('.account-parent-menu');
        if (menu) {
            menu.classList.add('d-none');
            menu.innerHTML = '';
        }
    }

    function initPicker(picker, options) {
        if (!picker || picker.dataset.pickerInit === '1') {
            return;
        }
        picker.dataset.pickerInit = '1';

        var hidden = picker.querySelector('.account-parent-value');
        var query = picker.querySelector('.account-parent-query');
        var menu = picker.querySelector('.account-parent-menu');
        if (!hidden || !query || !menu) {
            return;
        }

        function renderMenu(items) {
            menu.innerHTML = '';
            var noneBtn = document.createElement('button');
            noneBtn.type = 'button';
            noneBtn.className = 'list-group-item list-group-item-action py-2 text-muted';
            noneBtn.textContent = '— None (top level) —';
            noneBtn.addEventListener('click', function () {
                hidden.value = '';
                query.value = '';
                menu.classList.add('d-none');
            });
            menu.appendChild(noneBtn);

            if (!items.length) {
                var empty = document.createElement('div');
                empty.className = 'list-group-item text-muted small';
                empty.textContent = 'No matching accounts';
                menu.appendChild(empty);
            } else {
                items.slice(0, 12).forEach(function (item) {
                    var btn = document.createElement('button');
                    btn.type = 'button';
                    btn.className = 'list-group-item list-group-item-action py-2';
                    btn.textContent = item.label;
                    btn.addEventListener('click', function () {
                        hidden.value = String(item.id);
                        query.value = item.label;
                        menu.classList.add('d-none');
                    });
                    menu.appendChild(btn);
                });
            }
            menu.classList.remove('d-none');
        }

        function filterOptions(term) {
            var q = (term || '').trim().toLowerCase();
            if (!q) {
                return options.slice(0, 12);
            }
            return options.filter(function (item) {
                return item.label.toLowerCase().indexOf(q) !== -1;
            });
        }

        query.addEventListener('focus', function () {
            renderMenu(filterOptions(query.value));
        });

        query.addEventListener('input', function () {
            hidden.value = '';
            renderMenu(filterOptions(query.value));
        });

        query.addEventListener('keydown', function (e) {
            if (e.key === 'Escape') {
                menu.classList.add('d-none');
            }
        });

        picker._outsideHandler = function (e) {
            if (!picker.contains(e.target)) {
                menu.classList.add('d-none');
            }
        };
        document.addEventListener('click', picker._outsideHandler);

        var selectedId = hidden.value;
        if (selectedId) {
            var match = options.find(function (item) {
                return String(item.id) === String(selectedId);
            });
            if (match) {
                query.value = match.label;
            }
        }
    }

    function initAll(scope) {
        var root = scope || document;
        var options = parseParentOptions();
        root.querySelectorAll('.account-parent-picker').forEach(function (picker) {
            initPicker(picker, options);
        });
    }

    window.initFinanceAccountParentPickers = initAll;
    window.destroyFinanceAccountParentPickers = function (scope) {
        var root = scope || document;
        root.querySelectorAll('.account-parent-picker').forEach(function (picker) {
            destroyPicker(picker);
            delete picker.dataset.pickerInit;
        });
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () {
            initAll(document);
        });
    } else {
        initAll(document);
    }
})();
