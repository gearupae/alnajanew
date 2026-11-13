#!/usr/bin/env python3
"""Remove View (fa-eye) action buttons from list table templates."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "erp_project" / "templates"

# View-only action links (keep Edit / Delete / PDF).
PATTERNS = [
    re.compile(
        r"\s*<a\s+[^>]*class=\"[^\"]*btn[^\"]*\"[^>]*title=\"View[^\"]*\"[^>]*>\s*"
        r"<i class=\"fas fa-eye\"[^>]*></i>\s*</a>\s*",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"\s*<a\s+[^>]*class=\"[^\"]*btn[^\"]*\"[^>]*>\s*"
        r"<i class=\"fas fa-eye\"[^>]*></i>\s*</a>\s*",
        re.IGNORECASE | re.DOTALL,
    ),
    re.compile(
        r"\s*<a\s+href=\"[^\"]+\"\s+class=\"btn btn-sm btn-outline-secondary\">View</a>\s*",
        re.IGNORECASE,
    ),
]

SKIP_FILES = {
    "sales/estimate_form.html",
    "sales/estimate_detail.html",
    "contracts/contract_form.html",
    "purchase/pr_form.html",
}


def patch(text: str) -> str:
    for pat in PATTERNS:
        text = pat.sub("", text)
    return text


def main() -> None:
    n = 0
    for path in ROOT.rglob("*.html"):
        rel = str(path.relative_to(ROOT))
        if rel in SKIP_FILES:
            continue
        if "fa-eye" not in path.read_text(encoding="utf-8"):
            continue
        original = path.read_text(encoding="utf-8")
        updated = patch(original)
        if updated != original:
            path.write_text(updated, encoding="utf-8")
            n += 1
            print(rel)
    print(f"Updated {n} files")


if __name__ == "__main__":
    main()
