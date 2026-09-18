#!/usr/bin/env python3
"""
Capture Safety Point ERP user guide screenshots from the live system.

Usage:
  pip install playwright
  playwright install chromium
  python scripts/capture_user_guide_screenshots.py

Environment:
  GUIDE_BASE_URL   default https://sp.telldb.com
  GUIDE_USERNAME   default admin
  GUIDE_PASSWORD   default admin123
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / 'erp_project' / 'static' / 'img' / 'user-guide'
BASE_URL = os.environ.get('GUIDE_BASE_URL', 'https://alnajah.telldb.com').rstrip('/')
USERNAME = os.environ.get('GUIDE_USERNAME', 'admin')
PASSWORD = os.environ.get('GUIDE_PASSWORD', 'admin123')

# (filename, path, requires_login)
PAGES = [
    ('login.png', '/login/', False),
    ('dashboard.png', '/', True),
    ('settings-users.png', '/settings/users/', True),
    ('settings-roles.png', '/settings/roles/', True),
    ('settings-role-permissions.png', '/settings/roles/1/permissions/', True),
    ('settings-company.png', '/settings/company/', True),
    ('settings-approval.png', '/settings/approval-configuration/', True),
    ('settings-crm-kanban.png', '/settings/crm-kanban/', True),
    ('settings-expense-types.png', '/settings/sub-group-expense-types/', True),
    ('settings-audit-log.png', '/settings/audit-log/', True),
    ('finance-tax-codes.png', '/finance/tax-codes/', True),
    ('finance-accounts.png', '/finance/accounts/', True),
    ('finance-account-mapping.png', '/finance/account-mapping/', True),
    ('finance-accounting-settings.png', '/finance/settings/accounting/', True),
    ('finance-vat-returns.png', '/finance/vat-returns/', True),
    ('finance-journals.png', '/finance/journal/', True),
    ('finance-payments.png', '/finance/payments/', True),
    ('finance-bank-accounts.png', '/finance/bank-accounts/', True),
    ('finance-trial-balance.png', '/finance/reports/trial-balance/', True),
    ('crm-customers.png', '/crm/customers/', True),
    ('sales-estimates.png', '/sales/estimates/', True),
    ('sales-invoices.png', '/sales/invoices/', True),
    ('sales-credit-notes.png', '/sales/credit-notes/', True),
    ('projects-list.png', '/projects/', True),
    ('purchase-vendors.png', '/purchase/vendors/', True),
    ('purchase-requests.png', '/purchase/pr/', True),
    ('service-requests.png', '/service-request/', True),
    ('purchase-orders.png', '/purchase/po/', True),
    ('documents-list.png', '/documents/', True),
    ('contracts-list.png', '/contracts/', True),
    ('hr-dashboard.png', '/hr/dashboard/', True),
    ('hr-employees.png', '/hr/employees/', True),
    ('hr-leave.png', '/hr/leave/', True),
    ('hr-attendance.png', '/hr/attendance/', True),
    ('hr-payroll.png', '/hr/payroll/', True),
    ('inventory-items.png', '/inventory/items/', True),
    ('inventory-stock.png', '/inventory/stock/', True),
    ('inventory-stock-take.png', '/stock-take/', True),
    ('inventory-consumables.png', '/inventory/consumables/', True),
    ('fleet-vehicles.png', '/fleet/', True),
    ('reports-index.png', '/reports/', True),
    ('property-properties.png', '/property/properties/', True),
]


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print('Install playwright: pip install playwright && playwright install chromium', file=sys.stderr)
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    viewport = {'width': 1440, 'height': 900}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport=viewport, ignore_https_errors=True)
        page = context.new_page()

        # Login once for authenticated pages
        logged_in = False

        for filename, path, needs_login in PAGES:
            dest = OUT_DIR / filename
            url = f'{BASE_URL}{path}'
            print(f'Capturing {filename} <- {url}')

            if needs_login and not logged_in:
                page.goto(f'{BASE_URL}/login/', wait_until='networkidle', timeout=60000)
                page.fill('input[name="username"]', USERNAME)
                page.fill('input[name="password"]', PASSWORD)
                page.click('button[type="submit"]')
                page.wait_for_url('**/login/**', timeout=5000) if '/login/' in page.url else None
                page.wait_for_load_state('networkidle', timeout=60000)
                if '/login/' in page.url:
                    # wait for redirect away from login
                    try:
                        page.wait_for_function(
                            "() => !window.location.pathname.includes('/login')",
                            timeout=15000,
                        )
                    except Exception:
                        print(f'  WARN: still on login after submit — check credentials', file=sys.stderr)
                logged_in = True
                page.wait_for_timeout(800)

            page.goto(url, wait_until='networkidle', timeout=60000)
            page.wait_for_timeout(600)

            # Full page screenshot for list views
            page.screenshot(path=str(dest), full_page=False)
            print(f'  -> {dest}')

        browser.close()

    print(f'\nDone — {len(PAGES)} screenshots in {OUT_DIR}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
