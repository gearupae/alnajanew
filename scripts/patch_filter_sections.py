#!/usr/bin/env python3
"""Patch only <!-- Filters --> GET forms: toolbar class, no labels, icon buttons."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "erp_project" / "templates"

LABEL = re.compile(r"^\s*<label class=\"form-label[^\"]*\"[^>]*>.*?</label>\s*\n", re.M | re.I)
INLINE_LBL = re.compile(r"<label class=\"form-label small mb-0\">[^<]+</label>", re.I)


def patch_block(block: str) -> str:
    if 'method="get"' not in block and "method='get'" not in block:
        return block
    block = re.sub(
        r'<form method="get" class="(?!list-filters-toolbar)',
        '<form method="get" class="list-filters-toolbar ',
        block,
        count=1,
    )
    block = re.sub(
        r'<form method="get"(?! class)',
        '<form method="get" class="list-filters-toolbar"',
        block,
        count=1,
    )
    block = LABEL.sub("", block)
    block = INLINE_LBL.sub("", block)
    block = re.sub(
        r'<button type="submit" class="btn btn-primary([^"]*)">'
        r'\s*<i class="fas fa-filter me-1"></i>(?:Filter|Apply)\s*</button>',
        r'<button type="submit" class="btn btn-primary btn-filter-icon\1" '
        r'title="Apply filters" aria-label="Apply filters">'
        r'<i class="fas fa-filter" aria-hidden="true"></i></button>',
        block,
        flags=re.I,
    )
    block = re.sub(
        r'<button type="submit" class="btn ([^"]*)">\s*Filter\s*</button>',
        r'<button type="submit" class="btn btn-primary btn-filter-icon" '
        r'title="Apply filters" aria-label="Apply filters">'
        r'<i class="fas fa-filter" aria-hidden="true"></i></button>',
        block,
        flags=re.I,
    )
    block = re.sub(
        r'<a href="([^"]+)" class="btn btn-light([^"]*)">Clear</a>',
        r'<a href="\1" class="btn btn-light btn-filter-icon\2" '
        r'title="Clear filters" aria-label="Clear filters">'
        r'<i class="fas fa-times" aria-hidden="true"></i></a>',
        block,
        flags=re.I,
    )
    return block


def main() -> None:
    n = 0
    for path in ROOT.rglob("*.html"):
        text = path.read_text(encoding="utf-8")
        if "<!-- Filters -->" not in text:
            continue
        parts = re.split(r"(<!-- Filters -->)", text)
        if len(parts) < 3:
            continue
        out = parts[0]
        i = 1
        while i < len(parts):
            if parts[i] == "<!-- Filters -->":
                out += parts[i]
                chunk = parts[i + 1] if i + 1 < len(parts) else ""
                # Until next major section comment or end of card
                m = re.match(
                    r"(.*?</form>\s*</div>\s*</div>)",
                    chunk,
                    re.DOTALL,
                )
                if m:
                    block = m.group(1)
                    rest = chunk[len(block) :]
                    out += patch_block(block) + rest
                else:
                    out += patch_block(chunk)
                i += 2
            else:
                out += parts[i]
                i += 1
        if out != text:
            path.write_text(out, encoding="utf-8")
            n += 1
            print(path.relative_to(ROOT))
    print(f"Patched {n} files")


if __name__ == "__main__":
    main()
