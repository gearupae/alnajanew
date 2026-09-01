"""
Seed live demo data for Safety Point — fire & safety company, Abu Dhabi UAE.

Creates:
  - Chart of accounts + account mappings (if missing)
  - Single active tax code: VAT 5% Standard Rated
  - Customers, vendors, inventory items, estimates, employees

Idempotent — safe to re-run (uses SP-UAE-* reference tags).

Usage (production):
  cd /var/www/safetypoint/erp_project && source ../venv/bin/activate
  python manage.py seed_safety_point_uae
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

User = get_user_model()

TAG = "SP-UAE"
NOTE = "Seeded by seed_safety_point_uae"

CUSTOMERS = [
    ("001", "ADNOC Distribution", "100200300400003", "b2b", "amc", ["ff", "fa"]),
    ("002", "Etihad Towers Facilities Management", "100200300400004", "b2b", "project", ["ff", "em"]),
    ("003", "Yas Mall Operations LLC", "100200300400005", "b2b", "maintenance", ["ff", "fls"]),
    ("004", "Masdar City Development", "100200300400006", "b2b", "project", ["ff", "mep"]),
    ("005", "Al Reem Island Community LLC", "100200300400007", "b2b", "amc", ["ff", "fa"]),
    ("006", "Khalifa University Campus Services", "100200300400008", "b2b", "project", ["ff", "em"]),
]

VENDORS = [
    ("001", "Abu Dhabi Fire Equipment LLC", "Mohammed Al Dhaheri", "100300400500001"),
    ("002", "Gulf Safety Trading", "Salem Al Mazrouei", "100300400500002"),
    ("003", "Emirates Fire Systems FZE", "Khalid Al Nuaimi", "100300400500003"),
    ("004", "Al Safe Fire Protection", "Hamad Al Ketbi", "100300400500004"),
]

ITEM_GROUPS = [
    ("Fire Detection", False),
    ("Fire Suppression", False),
    ("Emergency & Exit Lighting", False),
    ("Fire Safety Consumables", True),
]

ITEMS = [
    ("FD-001", "Optical Smoke Detector – Addressable", "Fire Detection", "pcs", 95, 145),
    ("FD-002", "Heat Detector 58°C – Fixed", "Fire Detection", "pcs", 78, 115),
    ("FD-003", "Manual Call Point – Break Glass", "Fire Detection", "pcs", 52, 75),
    ("FS-001", "Sprinkler Head Upright 68°C K5.6", "Fire Suppression", "pcs", 32, 48),
    ("FS-002", "CO2 Fire Extinguisher 5kg", "Fire Suppression", "pcs", 195, 265),
    ("FS-003", "Fire Hose Reel 30m with Nozzle", "Fire Suppression", "pcs", 720, 980),
    ("EE-001", "LED Emergency Exit Sign – Running Man", "Emergency & Exit Lighting", "pcs", 62, 88),
    ("EE-002", "Twin Spot Emergency Light 3hr", "Emergency & Exit Lighting", "pcs", 105, 150),
    ("CS-001", "Intumescent Fire Sealant 310ml", "Fire Safety Consumables", "pcs", 15, 22),
    ("CS-002", "Fire Door Closer – Overhead", "Fire Safety Consumables", "pcs", 180, 250),
]

ESTIMATES = [
    ("001", "001", "approved", "commercial", "installation_with_amc"),
    ("002", "002", "sent", "commercial", "amc"),
    ("003", "003", "draft", "factories_industries", "maintenance"),
    ("004", "004", "approved", "commercial", "installation_without_amc"),
]

EMPLOYEES = [
    ("001", "Mohammed", "Al Dhaheri", "male", "OPS", "Operations Manager", 30000),
    ("002", "Ahmed", "Al Mansoori", "male", "OPS", "Site Supervisor", 16000),
    ("003", "Rashid", "Al Ketbi", "male", "OPS", "Field Technician", 9500),
    ("004", "Fatima", "Al Hashimi", "female", "FIN", "Accountant", 12000),
    ("005", "Sultan", "Al Kaabi", "male", "PROJ", "Project Manager", 27000),
    ("006", "Hamad", "Al Suwaidi", "male", "PROJ", "Project Engineer", 14500),
]

DEPARTMENTS = [
    ("OPS", "Operations"),
    ("FIN", "Finance"),
    ("PROJ", "Projects"),
    ("HR", "Human Resources"),
]

DESIGNATIONS = [
    ("Operations Manager", "OPS"),
    ("Site Supervisor", "OPS"),
    ("Field Technician", "OPS"),
    ("Accountant", "FIN"),
    ("Project Manager", "PROJ"),
    ("Project Engineer", "PROJ"),
]

WH_CODE = f"{TAG}-WH-AD"


class Command(BaseCommand):
    help = "Seed Safety Point Abu Dhabi fire & safety demo data (live ERP)"

    @transaction.atomic
    def handle(self, *args, **options):
        admin = User.objects.filter(is_superuser=True).first() or User.objects.filter(is_active=True).first()
        if not admin:
            self.stderr.write(self.style.ERROR("No active user found."))
            return

        today = date.today()
        self.stdout.write("Ensuring chart of accounts and mappings...")
        call_command("seed_standard_coa", verbosity=0)
        call_command("setup_account_mappings", verbosity=0)

        tax_code = self._seed_vat5_only()
        self._update_company_settings()
        counts = {
            "customers": self._seed_customers(admin),
            "vendors": self._seed_vendors(admin),
            "item_groups": 0,
            "items": 0,
            "stock": 0,
            "estimates": 0,
            "employees": 0,
        }
        counts["item_groups"], counts["items"] = self._seed_items(tax_code, admin)
        counts["stock"] = self._seed_stock(admin, today)
        counts["estimates"] = self._seed_estimates(admin, today, tax_code)
        counts["employees"] = self._seed_employees(today)

        self.stdout.write(self.style.SUCCESS("\nSafety Point UAE seed complete:"))
        for key, val in counts.items():
            self.stdout.write(f"  {key}: {val} new records")
        self.stdout.write(self.style.SUCCESS(f"  tax_code: {tax_code.code} ({tax_code.rate}%)"))

    def _seed_vat5_only(self):
        from apps.finance.models import Account, AccountType, TaxCode

        vat_payable = Account.objects.filter(is_active=True, code="2200").first()
        if not vat_payable:
            vat_payable = Account.objects.filter(
                is_active=True, account_type=AccountType.LIABILITY, name__icontains="vat"
            ).first()
        vat_recoverable = Account.objects.filter(is_active=True, code="1310").first()
        if not vat_recoverable:
            vat_recoverable = Account.objects.filter(
                is_active=True, account_type=AccountType.ASSET, name__icontains="vat"
            ).first()

        tax_code, created = TaxCode.objects.update_or_create(
            code="VAT5",
            defaults={
                "name": "VAT 5% - Standard Rated",
                "tax_type": "standard",
                "rate": Decimal("5.00"),
                "description": "UAE standard VAT rate (5%) for fire & safety goods and services.",
                "is_default": True,
                "is_active": True,
                "sales_account": vat_payable,
                "purchase_account": vat_recoverable,
            },
        )
        deactivated = TaxCode.objects.exclude(code="VAT5").update(is_default=False, is_active=False)
        action = "Created" if created else "Updated"
        self.stdout.write(self.style.SUCCESS(f"  {action} VAT5 (5% only); deactivated {deactivated} other tax code(s)"))
        return tax_code

    def _update_company_settings(self):
        from apps.settings_app.models import CompanySettings

        cs = CompanySettings.get_settings()
        cs.company_name = "Safety Point"
        cs.address = "Mussafah Industrial Area, Abu Dhabi, United Arab Emirates"
        cs.phone = "+971 2 555 0100"
        cs.email = "info@safetypoint.ae"
        cs.website = "http://sp.telldb.com"
        cs.tax_id = cs.tax_id or "100123456700003"
        cs.currency = "AED"
        cs.timezone = "Asia/Dubai"
        cs.save()
        self.stdout.write("  Updated company profile (Abu Dhabi)")

    def _seed_customers(self, admin) -> int:
        from apps.crm.models import Customer

        created = 0
        for seq, name, trn, segment, job_type, scope in CUSTOMERS:
            ref = f"{TAG}-CUST-{seq}"
            _, was_created = Customer.objects.get_or_create(
                name=f"[{TAG}] {name}",
                defaults={
                    "email": f"contact.{seq}@safetypoint-demo.ae",
                    "phone": f"+9712{int(seq):07d}",
                    "company": name,
                    "address": f"{name}, Abu Dhabi, UAE",
                    "city": "Abu Dhabi",
                    "country": "United Arab Emirates",
                    "trn": trn,
                    "scope": scope,
                    "job_type": job_type,
                    "business_segment": segment,
                    "payment_terms": "Net 30",
                    "credit_limit": Decimal("500000.00"),
                    "status": "active",
                    "customer_type": "customer",
                    "notes": f"{NOTE} ref {ref}",
                    "created_by": admin,
                },
            )
            if was_created:
                created += 1
        return created

    def _seed_vendors(self, admin) -> int:
        from apps.purchase.models import Vendor

        created = 0
        for seq, name, contact, trn in VENDORS:
            _, was_created = Vendor.objects.get_or_create(
                name=f"[{TAG}] {name}",
                defaults={
                    "contact_person": contact,
                    "email": f"orders.{seq}@safetypoint-vendor.ae",
                    "phone": f"+97150{int(seq):07d}",
                    "address": f"Mussafah ICAD, Abu Dhabi, UAE",
                    "city": "Abu Dhabi",
                    "country": "United Arab Emirates",
                    "trn": trn,
                    "payment_terms": "Net 30",
                    "credit_limit": Decimal("200000.00"),
                    "status": "active",
                    "notes": NOTE,
                    "created_by": admin,
                },
            )
            if was_created:
                created += 1
        return created

    def _seed_items(self, tax_code, admin) -> tuple[int, int]:
        from apps.inventory.models import Category, Item, ItemGroup

        cat, _ = Category.objects.get_or_create(
            code=f"{TAG}-CAT",
            defaults={"name": f"[{TAG}] Fire & Safety Products", "description": NOTE},
        )

        group_map: dict[str, ItemGroup] = {}
        groups_created = 0
        for gname, hide_pdf in ITEM_GROUPS:
            grp, was_created = ItemGroup.objects.get_or_create(
                name=f"[{TAG}] {gname}",
                defaults={"hide_items_on_pdf": hide_pdf},
            )
            group_map[gname] = grp
            if was_created:
                groups_created += 1

        items_created = 0
        for code_suffix, name, group_name, unit, purchase, selling in ITEMS:
            item_code = f"{TAG}-{code_suffix}"
            item, was_created = Item.objects.get_or_create(
                item_code=item_code,
                defaults={
                    "name": name,
                    "description": f"{NOTE} – {name}",
                    "category": cat,
                    "item_type": "product",
                    "status": "active",
                    "unit": unit,
                    "purchase_price": Decimal(str(purchase)),
                    "selling_price": Decimal(str(selling)),
                    "minimum_selling_price": Decimal(str(purchase)),
                    "minimum_stock": Decimal("5"),
                    "tax_code": tax_code,
                    "created_by": admin,
                },
            )
            if was_created:
                items_created += 1
            else:
                item.tax_code = tax_code
                item.save(update_fields=["tax_code"])
            item.item_groups.set([group_map[group_name]])
        return groups_created, items_created

    def _seed_stock(self, admin, today: date) -> int:
        from apps.inventory.models import Item, Stock, StockMovement, Warehouse

        wh, _ = Warehouse.objects.get_or_create(
            code=WH_CODE,
            defaults={
                "name": "Safety Point Abu Dhabi Warehouse",
                "address": "Mussafah Industrial Area, Abu Dhabi, UAE",
                "contact_person": "Store Keeper",
                "phone": "+97125550101",
                "status": "active",
                "is_active": True,
                "created_by": admin,
            },
        )

        stock_qty = {
            "FD-001": Decimal("120"),
            "FD-002": Decimal("80"),
            "FD-003": Decimal("60"),
            "FS-001": Decimal("200"),
            "FS-002": Decimal("40"),
            "FS-003": Decimal("12"),
            "EE-001": Decimal("75"),
            "EE-002": Decimal("45"),
            "CS-001": Decimal("300"),
            "CS-002": Decimal("25"),
        }

        created = 0
        for item in Item.objects.filter(item_code__startswith=f"{TAG}-"):
            suffix = item.item_code.removeprefix(f"{TAG}-")
            qty = stock_qty.get(suffix, Decimal("50"))
            ref = f"{TAG}-OB-{item.item_code}"
            if StockMovement.objects.filter(reference=ref).exists():
                continue
            movement = StockMovement.objects.create(
                item=item,
                warehouse=wh,
                movement_type="in",
                source="opening",
                quantity=qty,
                unit_cost=item.purchase_price or Decimal("1.00"),
                reference=ref,
                notes=f"Opening stock. {NOTE}",
                movement_date=today - timedelta(days=14),
                posted=False,
                created_by=admin,
            )
            movement.update_stock()
            created += 1
        return created

    def _seed_estimates(self, admin, today: date, tax_code) -> int:
        from apps.crm.models import Customer
        from apps.inventory.models import Item
        from apps.sales.models import Estimate, EstimateItem

        line_groups = [
            ("Fire Detection System", ["FD-001", "FD-002", "FD-003"]),
            ("Suppression Equipment", ["FS-001", "FS-002", "FS-003"]),
            ("Emergency Lighting", ["EE-001", "EE-002"]),
        ]

        created = 0
        for seq, cust_seq, status, occupancy, work_type in ESTIMATES:
            cust_name = CUSTOMERS[int(cust_seq) - 1][1]
            customer = Customer.objects.filter(name=f"[{TAG}] {cust_name}").first()
            if not customer:
                customer = Customer.objects.filter(name__startswith=f"[{TAG}]").order_by("pk").first()
            if not customer:
                continue

            estimate, was_created = Estimate.objects.get_or_create(
                notes=f"{NOTE} ref {TAG}-EST-{seq}",
                customer=customer,
                defaults={
                    "assigned_to": admin,
                    "prepared_by": admin.get_full_name() or admin.username,
                    "type_of_occupancy": occupancy,
                    "type_of_work": work_type,
                    "scope_of_work": f"Fire & life safety works for {cust_name}, Abu Dhabi.",
                    "date": today - timedelta(days=5 + int(seq)),
                    "valid_until": today + timedelta(days=30),
                    "status": status,
                    "client_note": "Quotation for fire alarm, suppression, and emergency lighting.",
                    "show_group_totals_on_pdf": True,
                    "created_by": admin,
                },
            )
            if not was_created:
                continue

            created += 1
            sort_order = 0
            for group_name, item_codes in line_groups:
                for code_suffix in item_codes:
                    item = Item.objects.filter(item_code=f"{TAG}-{code_suffix}").first()
                    if not item:
                        continue
                    EstimateItem.objects.create(
                        estimate=estimate,
                        group_name=group_name,
                        sort_order=sort_order,
                        inventory_item=item,
                        description=item.name,
                        quantity=Decimal("10") if "CS" not in code_suffix else Decimal("5"),
                        unit_price=item.selling_price or item.purchase_price,
                        profit_type="percent",
                        profit_value=Decimal("20"),
                        tax_code=tax_code,
                        is_vat_inclusive=False,
                    )
                    sort_order += 1
            estimate.calculate_totals()
        return created

    def _seed_employees(self, today: date) -> int:
        from apps.hr.models import Department, Designation, Employee
        from apps.settings_app.models import Company

        co, _ = Company.objects.get_or_create(
            name="Safety Point (Abu Dhabi)",
            defaults={
                "country": "uae",
                "trade_license_number": "CN-AD-2024-001",
                "address": "Mussafah Industrial Area, Abu Dhabi, UAE",
            },
        )

        dept_map = {}
        for code, name in DEPARTMENTS:
            dept, _ = Department.objects.get_or_create(code=f"{TAG}-{code}", defaults={"name": name})
            dept_map[code] = dept

        desig_map = {}
        for title, dept_code in DESIGNATIONS:
            desig, _ = Designation.objects.get_or_create(name=title, department=dept_map[dept_code])
            desig_map[title] = desig

        created = 0
        for seq, first, last, gender, dept_code, desig_title, salary in EMPLOYEES:
            code = f"{TAG}-{seq}"
            _, was_created = Employee.objects.update_or_create(
                employee_code=code,
                defaults={
                    "first_name": first,
                    "last_name": last,
                    "email": f"{first.lower()}.{last.lower().replace(' ', '')}@safetypoint.ae",
                    "phone": f"+97150{int(seq):07d}",
                    "gender": gender,
                    "department": dept_map[dept_code],
                    "designation": desig_map[desig_title],
                    "date_of_joining": date(2024, max(1, int(seq) % 12), 1),
                    "status": "active",
                    "basic_salary": Decimal(str(salary)),
                    "company": co,
                    "location": "uae",
                    "emirates_id": f"784-AD-{seq.zfill(7)}-1",
                    "visa_number": f"AD-VISA-{seq}",
                    "visa_expiry": today.replace(year=today.year + 2),
                },
            )
            if was_created:
                created += 1
        return created
