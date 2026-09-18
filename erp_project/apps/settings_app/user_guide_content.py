"""
Structured Al Najah ERP user guide content.

Screenshots are stored under static/img/user-guide/ and captured by
scripts/capture_user_guide_screenshots.py against https://alnajah.telldb.com/
"""

USER_GUIDE_SECTIONS = [
    {
        'id': 'getting-started',
        'title': 'Getting Started',
        'icon': 'fa-sign-in-alt',
        'intro': (
            'Al Najah ERP is a modular business system. Start by signing in, '
            'then use the top navigation bar to reach CRM, Sales, Purchase, Finance, '
            'Inventory, HR, and other modules based on your assigned role.'
        ),
        'topics': [
            {
                'id': 'login',
                'title': 'Logging in',
                'screenshot': 'login.png',
                'steps': [
                    'Open your browser and go to https://alnajah.telldb.com/login/',
                    'Enter your username and password provided by your administrator.',
                    'Click Sign In. On success you are redirected to the Dashboard.',
                    'Use Remember me only on trusted personal devices.',
                    'If you see an invalid password message, contact your admin to reset access.',
                ],
                'tips': [
                    'The login page shows the Al Najah branding and company logo.',
                    'After 8 hours of inactivity your session expires and you must sign in again.',
                ],
            },
            {
                'id': 'dashboard',
                'title': 'Dashboard & navigation',
                'screenshot': 'dashboard.png',
                'steps': [
                    'After login the Dashboard (home) shows your main workspace entry point.',
                    'The dark top bar lists every module you are permitted to use.',
                    'Click a module name to open its submenu (Sales, Finance, HR, etc.).',
                    'The gear icon on the right opens Settings (admin users).',
                    'The bell icon shows in-app notifications; your profile menu is on the far right.',
                ],
                'tips': [
                    'Modules you cannot access are hidden — your role controls what appears.',
                    'Click the logo at top-left to return to the Dashboard anytime.',
                ],
            },
        ],
    },
    {
        'id': 'settings-admin',
        'title': 'Settings & Administration',
        'icon': 'fa-cog',
        'intro': (
            'Administrators configure users, roles, company profile, approvals, and '
            'module-specific settings from the Settings gear menu. Complete these steps '
            'before rolling the system out to your team.'
        ),
        'topics': [
            {
                'id': 'users',
                'title': 'User management',
                'screenshot': 'settings-users.png',
                'steps': [
                    'Go to Settings → Users (/settings/users/).',
                    'Review existing users and their active/inactive status.',
                    'Click Add User to create a new login: username, name, email, password.',
                    'Assign one or more Roles to each user — roles control module access.',
                    'Use Edit to change roles or deactivate users with the toggle action.',
                ],
                'tips': [
                    'HR employees can also receive auto-provisioned logins when saved with an ERP role.',
                    'Deactivate users instead of deleting them to preserve audit history.',
                ],
            },
            {
                'id': 'roles',
                'title': 'Roles',
                'screenshot': 'settings-roles.png',
                'steps': [
                    'Go to Settings → Roles (/settings/roles/).',
                    'Default roles include Super Admin, Admin, Manager, Sales, Purchase, Accountant, and Employee.',
                    'Click Add Role to create a custom role with a name and description.',
                    'Use Edit to rename a role or Permissions to configure access.',
                ],
            },
            {
                'id': 'role-permissions',
                'title': 'Role permissions',
                'screenshot': 'settings-role-permissions.png',
                'steps': [
                    'From Settings → Roles, click Permissions on any role.',
                    'The matrix lists every module: CRM, Sales, Purchase, Inventory, Finance, Projects, HR, Documents, Contracts, Fleet, Reports, Property, Service Request, Settings.',
                    'Tick View, Create, Edit, Delete, and Approve per module as needed.',
                    'Click Save Permissions. Users with that role gain access immediately on next page load.',
                ],
                'tips': [
                    'Super Admin users bypass all permission checks.',
                    'Grant Settings access only to trusted administrators.',
                    'Use Approve permission for users who must action workflow items (PR, estimates, leave, etc.).',
                ],
            },
            {
                'id': 'company',
                'title': 'Company settings',
                'screenshot': 'settings-company.png',
                'steps': [
                    'Go to Settings → Company (/settings/company/).',
                    'Enter Company Name (appears on PDFs and login branding), address, phone, email, website.',
                    'Set VAT / TRN number — required on UAE tax invoices and quotations.',
                    'Upload your company logo for estimates, invoices, and purchase orders.',
                    'Configure SMTP email settings so the system can send quotations, POs, and payslips.',
                    'Set default estimate text templates and signature images for PDF documents.',
                ],
                'tips': [
                    'Company name (e.g. Al Najah) is shown on the login page and document footers.',
                    'Use Settings → Companies for multi-entity setups with separate bank details.',
                ],
            },
            {
                'id': 'approval-config',
                'title': 'Approval configuration',
                'screenshot': 'settings-approval.png',
                'steps': [
                    'Go to Settings → Approval Configuration.',
                    'Configure approval chains for: Purchase Requests, Inventory Requests, Inventory Items, Stock Adjustments, Service Requests, Sales Estimates, Projects, Project Conversion, Project Operation Access, and Leave Requests.',
                    'For each module set the number of approval levels and assign approver roles or users.',
                    'Save each section. Submitted documents route through the configured chain.',
                ],
            },
            {
                'id': 'crm-kanban',
                'title': 'CRM Kanban stages',
                'screenshot': 'settings-crm-kanban.png',
                'steps': [
                    'Go to Settings → CRM Kanban to define lead pipeline columns.',
                    'Add stages (e.g. New Lead, Qualified, Proposal, Won, Lost).',
                    'Enable Converts to customer on exactly one stage — leads dropped there become customers.',
                    'Set sort order to control column sequence on the CRM board.',
                ],
            },
            {
                'id': 'expense-types',
                'title': 'Expense types (inventory sub-groups)',
                'screenshot': 'settings-expense-types.png',
                'steps': [
                    'Go to Settings → Expense types to map inventory sub-group labels to expense categories.',
                    'Used when posting project or consumable costs to the chart of accounts.',
                ],
            },
            {
                'id': 'audit-log',
                'title': 'Audit log',
                'screenshot': 'settings-audit-log.png',
                'steps': [
                    'Go to Settings → Audit Log to review system activity.',
                    'Filter by user, action (create, update, delete, login), module, and date.',
                    'Use for compliance reviews and troubleshooting who changed a record.',
                ],
            },
        ],
    },
    {
        'id': 'finance-setup',
        'title': 'Finance Setup',
        'icon': 'fa-coins',
        'intro': (
            'Configure tax codes, chart of accounts, and accounting settings before '
            'creating sales invoices or vendor bills. UAE VAT compliance is built in.'
        ),
        'topics': [
            {
                'id': 'tax-codes',
                'title': 'Tax codes (VAT)',
                'screenshot': 'finance-tax-codes.png',
                'steps': [
                    'Go to Finance → Tax Codes (/finance/tax-codes/).',
                    'Review standard UAE codes: Standard Rated 5%, Zero Rated, Exempt, Out of Scope.',
                    'Click Add Tax Code to create a new code with name, rate %, and type.',
                    'Assign tax codes to items (Inventory), estimate/invoice lines (Sales), and vendor bill lines (Purchase).',
                    'Tax codes drive VAT return calculations and FTA reporting.',
                ],
                'tips': [
                    'Set up tax codes before importing items or creating your first invoice.',
                    'Use Tax Reconciliation report (Finance → Reports) to verify VAT balances.',
                ],
            },
            {
                'id': 'chart-of-accounts',
                'title': 'Chart of accounts',
                'screenshot': 'finance-accounts.png',
                'steps': [
                    'Go to Finance → Chart of Accounts (/finance/accounts/).',
                    'Review the standard COA or run seed_standard_coa management command for UAE defaults.',
                    'Add accounts with code, name, type (Asset, Liability, Equity, Income, Expense), and category.',
                    'Mark bank accounts and cash accounts appropriately for reconciliation.',
                ],
            },
            {
                'id': 'account-mapping',
                'title': 'Account mapping',
                'screenshot': 'finance-account-mapping.png',
                'steps': [
                    'Go to Finance → Account Mapping.',
                    'Map transaction types (Sales, Purchase, Inventory, Payroll, etc.) to GL accounts.',
                    'Required for automatic journal entries when posting invoices, bills, and stock movements.',
                ],
            },
            {
                'id': 'accounting-settings',
                'title': 'Accounting settings',
                'screenshot': 'finance-accounting-settings.png',
                'steps': [
                    'Go to Finance → Accounting Settings.',
                    'Set fiscal year start, default currency (AED), inventory valuation method, and corporate tax options.',
                    'Configure opening balances and period locking before go-live.',
                ],
            },
            {
                'id': 'vat-returns',
                'title': 'VAT returns',
                'screenshot': 'finance-vat-returns.png',
                'steps': [
                    'Go to Finance → VAT Returns to prepare UAE FTA returns.',
                    'Create a return for a period, review computed boxes, post, and track submission status.',
                ],
            },
        ],
    },
    {
        'id': 'crm',
        'title': 'CRM',
        'icon': 'fa-users',
        'intro': 'Manage leads and customers on a Kanban board. Convert qualified leads to customers for Sales and Projects.',
        'topics': [
            {
                'id': 'crm-board',
                'title': 'CRM / Leads board',
                'screenshot': 'crm-customers.png',
                'steps': [
                    'Open CRM from the top navigation (/crm/customers/).',
                    'View leads and customers as Kanban cards grouped by pipeline stage.',
                    'Drag cards between stages or click a card to open details.',
                    'Add new leads with the Add button; assign salesperson and contact details.',
                    'Upload trade licence and documents; track opportunity value on qualifying stages.',
                    'When a lead reaches the "Won" stage (configured in CRM Kanban settings) it converts to a customer.',
                ],
            },
        ],
    },
    {
        'id': 'sales',
        'title': 'Sales',
        'icon': 'fa-shopping-cart',
        'intro': 'Create estimates (quotations), convert to projects, issue invoices and credit notes.',
        'topics': [
            {
                'id': 'estimates',
                'title': 'Estimates (quotations)',
                'screenshot': 'sales-estimates.png',
                'steps': [
                    'Go to Sales → Estimates (/sales/estimates/).',
                    'Create a new estimate: select customer, add line items from inventory or free text.',
                    'Apply tax codes per line; set scope of work, terms, and PDF display options.',
                    'Submit for approval if configured; email PDF to customer or share public link.',
                    'Mark Won/Lost; won estimates can convert to Projects.',
                ],
            },
            {
                'id': 'invoices',
                'title': 'Invoices',
                'screenshot': 'sales-invoices.png',
                'steps': [
                    'Go to Sales → Invoices (/sales/invoices/).',
                    'Create from estimate or standalone; post to generate GL entries and AR.',
                    'Record customer payments in Finance → Payments.',
                ],
            },
            {
                'id': 'credit-notes',
                'title': 'Credit notes',
                'screenshot': 'sales-credit-notes.png',
                'steps': [
                    'Go to Sales → Credit Notes to issue refunds or invoice corrections.',
                    'Link to original invoice where applicable; posts reversing VAT and revenue entries.',
                ],
            },
        ],
    },
    {
        'id': 'projects',
        'title': 'Projects',
        'icon': 'fa-project-diagram',
        'intro': 'Track jobs from estimate conversion through tasks, expenses, gate passes, and technician attendance.',
        'topics': [
            {
                'id': 'project-list',
                'title': 'Projects & tasks',
                'screenshot': 'projects-list.png',
                'steps': [
                    'Go to Projects → All Projects (/projects/).',
                    'View project status, customer, progress, and linked estimate.',
                    'Open a project to manage tasks, items, expenses, documents, and team assignments.',
                    'Use All Tasks for cross-project task lists; Project Expenses for cost tracking.',
                ],
            },
        ],
    },
    {
        'id': 'purchase',
        'title': 'Purchase',
        'icon': 'fa-truck',
        'intro': 'Manage vendors, purchase requests, service requests, purchase orders, and vendor bills.',
        'topics': [
            {
                'id': 'vendors',
                'title': 'Vendors',
                'screenshot': 'purchase-vendors.png',
                'steps': [
                    'Go to Purchase → Vendors (/purchase/vendors/).',
                    'Maintain vendor master data: contact, TRN, payment terms, and documents.',
                ],
            },
            {
                'id': 'purchase-requests',
                'title': 'Purchase requests',
                'screenshot': 'purchase-requests.png',
                'steps': [
                    'Go to Purchase → Purchase Requests (/purchase/pr/).',
                    'Raise internal requests for materials or services; route through approval workflow.',
                    'Approved PRs convert to Purchase Orders.',
                ],
            },
            {
                'id': 'service-requests',
                'title': 'Service requests',
                'screenshot': 'service-requests.png',
                'steps': [
                    'Go to Purchase → Service Requests (/service-request/).',
                    'Track subcontractor or maintenance work separately from material PRs.',
                ],
            },
            {
                'id': 'purchase-orders',
                'title': 'Purchase orders & bills',
                'screenshot': 'purchase-orders.png',
                'steps': [
                    'Go to Purchase → Purchase Orders (/purchase/po/) to issue POs to vendors.',
                    'Receive goods and match to Vendor Bills (/purchase/bills/).',
                    'Use Debit Notes for vendor credit adjustments.',
                ],
            },
        ],
    },
    {
        'id': 'documents-contracts',
        'title': 'Documents & Contracts',
        'icon': 'fa-folder-open',
        'intro': 'Store company documents with expiry alerts and manage customer contracts.',
        'topics': [
            {
                'id': 'documents',
                'title': 'Documents',
                'screenshot': 'documents-list.png',
                'steps': [
                    'Go to Documents → All Documents (/documents/).',
                    'Upload files linked to customers, projects, or standalone.',
                    'Configure Document Types with expiry alert days for licence renewals.',
                ],
            },
            {
                'id': 'contracts',
                'title': 'Contracts',
                'screenshot': 'contracts-list.png',
                'steps': [
                    'Go to Documents → Contracts (/contracts/).',
                    'Create contracts with customer, value, dates, scope of work, and PDF generation.',
                ],
            },
        ],
    },
    {
        'id': 'finance-operations',
        'title': 'Finance Operations',
        'icon': 'fa-university',
        'intro': 'Day-to-day accounting: journals, payments, banking, budgets, and statutory reports.',
        'topics': [
            {
                'id': 'journals',
                'title': 'Journal entries',
                'screenshot': 'finance-journals.png',
                'steps': [
                    'Go to Finance → Journal Entries (/finance/journal/).',
                    'Create manual journals; post to update the general ledger.',
                    'Use Reverse for correcting posted entries in locked periods.',
                ],
            },
            {
                'id': 'payments',
                'title': 'Payments',
                'screenshot': 'finance-payments.png',
                'steps': [
                    'Go to Finance → Payments to record customer receipts and vendor payments.',
                    'Allocate to open invoices or bills; posts to bank and AR/AP accounts.',
                ],
            },
            {
                'id': 'banking',
                'title': 'Bank accounts & reconciliation',
                'screenshot': 'finance-bank-accounts.png',
                'steps': [
                    'Set up Bank Accounts, import Bank Statements, and run Bank Reconciliation.',
                    'Match statement lines to payments and journal entries.',
                ],
            },
            {
                'id': 'finance-reports',
                'title': 'Financial reports',
                'screenshot': 'finance-trial-balance.png',
                'steps': [
                    'Open Finance → Reports submenu for Trial Balance, P&L, Balance Sheet, Cash Flow.',
                    'Use AR/AP Aging, VAT Report, Corporate Tax, and General Ledger as needed.',
                ],
            },
        ],
    },
    {
        'id': 'hr',
        'title': 'HR',
        'icon': 'fa-user-friends',
        'intro': 'Employees, leave, attendance, payroll, and UAE compliance (WPS, gratuity, document expiry).',
        'topics': [
            {
                'id': 'hr-dashboard',
                'title': 'HR dashboard',
                'screenshot': 'hr-dashboard.png',
                'steps': [
                    'Go to HR → Dashboard for headcount, leave pending, document expiry, and attendance summary.',
                ],
            },
            {
                'id': 'employees',
                'title': 'Employees',
                'screenshot': 'hr-employees.png',
                'steps': [
                    'Go to HR → Employees to maintain staff records, designation, department, and company.',
                    'Link ERP login and assign role for self-service attendance and payslips.',
                    'Store visa, labour card, and document expiry dates for compliance alerts.',
                ],
            },
            {
                'id': 'leave',
                'title': 'Leave management',
                'screenshot': 'hr-leave.png',
                'steps': [
                    'Configure Leave Types; employees apply via HR → Leave requests.',
                    'Managers and HR approve through the configured approval chain.',
                    'View Leave Calendar and Pending (HR) queue.',
                ],
            },
            {
                'id': 'attendance',
                'title': 'Attendance',
                'screenshot': 'hr-attendance.png',
                'steps': [
                    'Go to HR → Attendance → Records for daily clock-in/out.',
                    'Configure Attendance Settings, Holidays, and import CSV from biometric devices.',
                    'Technicians can punch via public link tied to projects.',
                ],
            },
            {
                'id': 'payroll',
                'title': 'Payroll',
                'screenshot': 'hr-payroll.png',
                'steps': [
                    'Go to HR → Payroll to run monthly payroll from employee salary templates.',
                    'Generate payslips and email to employees; posts to Finance GL when configured.',
                ],
            },
        ],
    },
    {
        'id': 'inventory',
        'title': 'Inventory',
        'icon': 'fa-boxes',
        'intro': 'Items, warehouses, stock movements, consumables, and stock take with barcode scanning.',
        'topics': [
            {
                'id': 'items',
                'title': 'Items & categories',
                'screenshot': 'inventory-items.png',
                'steps': [
                    'Go to Inventory → Items (/inventory/items/) to create products and services.',
                    'Set SKU, unit, cost, selling price, tax code, and item groups for estimates.',
                    'Use Categories and Warehouses to organise stock locations.',
                ],
            },
            {
                'id': 'stock',
                'title': 'Stock levels & movements',
                'screenshot': 'inventory-stock.png',
                'steps': [
                    'View Stock Levels for on-hand quantities per warehouse.',
                    'Stock Movements log receipts, issues, and adjustments (may require approval).',
                ],
            },
            {
                'id': 'stock-take',
                'title': 'Stock take',
                'screenshot': 'inventory-stock-take.png',
                'steps': [
                    'Go to Inventory → Stock Take to start a count session.',
                    'Scan barcodes via web camera or the Safety Point Scan mobile app.',
                    'Complete session and export PDF report with variances.',
                ],
            },
            {
                'id': 'consumables',
                'title': 'Medical consumables',
                'screenshot': 'inventory-consumables.png',
                'steps': [
                    'Use Request Items for internal consumable requests tied to projects.',
                    'Run Inventory Reports and Aging Report for usage analytics.',
                ],
            },
        ],
    },
    {
        'id': 'fleet',
        'title': 'Assets / Fleet',
        'icon': 'fa-truck',
        'intro': 'Fleet vehicle register, gate passes, and maintenance tracking.',
        'topics': [
            {
                'id': 'fleet',
                'title': 'Fleet vehicles',
                'screenshot': 'fleet-vehicles.png',
                'steps': [
                    'Go to Assets → Fleet (/fleet/vehicles/) to register vehicles.',
                    'Track registration, insurance expiry, assignments, and gate pass history.',
                ],
            },
        ],
    },
    {
        'id': 'reports',
        'title': 'Reports',
        'icon': 'fa-chart-line',
        'intro': 'Cross-module analytics for leads, sales, and project performance.',
        'topics': [
            {
                'id': 'reports-hub',
                'title': 'Reports hub',
                'screenshot': 'reports-index.png',
                'steps': [
                    'Go to Reports → All Reports (/reports/) for the report catalogue.',
                    'Lead Report — pipeline and conversion metrics.',
                    'Sales Report — estimate and invoice performance.',
                    'Project P&L, Customer Progress, and Period Wise reports for operations.',
                ],
            },
        ],
    },
    {
        'id': 'property',
        'title': 'Property Management',
        'icon': 'fa-home',
        'intro': 'Properties, tenants, leases, PDC cheques, and rent invoicing (enable in NAV_HIDDEN_MODULES to show in menu).',
        'topics': [
            {
                'id': 'properties',
                'title': 'Properties & tenants',
                'screenshot': 'property-properties.png',
                'steps': [
                    'Go to Property → Properties to register buildings and units.',
                    'Manage Tenants and Leases with rent schedules.',
                    'Track PDC Cheques and bank reconciliation for rent collections.',
                ],
            },
        ],
    },
]
