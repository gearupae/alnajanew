#!/usr/bin/env python3
"""Normalize list-page GET filter forms: single row, no labels, icon filter/clear."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "erp_project" / "templates"

ROW_FORM = re.compile(
    r'class="((?:[^"]*\s+)?)row g-(?:2|3)(?:\s+[^"]*)?align-items-end"',
    re.IGNORECASE,
)
FLEX_FORM = re.compile(
    r'class="d-flex flex-wrap align-items-end[^"]*"',
    re.IGNORECASE,
)
ROW_FORM_PLAIN = re.compile(
    r'class="row g-(?:2|3)(?!")[^"]*"',
    re.IGNORECASE,
)
INLINE_LBL = re.compile(
    r'<label class="form-label small mb-0">[^<]+</label>',
    re.IGNORECASE,
)
TEXT_FILTER_BTN = re.compile(
    r'<button type="submit" class="btn ([^"]*)">\s*Filter\s*</button>',
    re.IGNORECASE,
)
SEARCH_BTN = re.compile(
    r'<button type="submit" class="btn btn-primary me-2"><i class="fas fa-search me-1"></i>Search</button>',
    re.IGNORECASE,
)
LABEL_LINE = re.compile(
    r"^\s*<label class=\"form-label[^\"]*\"[^>]*>.*?</label>\s*\n",
    re.MULTILINE | re.IGNORECASE,
)
FILTER_BTN = re.compile(
    r'<button type="submit" class="btn btn-primary([^"]*)">'
    r'\s*<i class="fas fa-filter me-1"></i>(?:Filter|Apply)\s*</button>',
    re.IGNORECASE,
)
CLEAR_BTN = re.compile(
    r'<a href="([^"]+)" class="btn btn-(?:light|outline-secondary)([^"]*)">Clear</a>',
    re.IGNORECASE,
)
APPLY_BTN_NO_ICON = re.compile(
    r'<button type="submit" class="btn btn-primary([^"]*)">\s*Apply\s*</button>',
    re.IGNORECASE,
)


def _add_toolbar_class(class_attr: str) -> str:
    if "list-filters-toolbar" in class_attr:
        return class_attr
    return f'class="list-filters-toolbar {class_attr[7:]}'


def patch_form_class(html: str) -> str:
    def repl_row(m: re.Match) -> str:
        return _add_toolbar_class(m.group(0))

    def repl_flex(m: re.Match) -> str:
        return _add_toolbar_class(m.group(0))

    html = ROW_FORM.sub(repl_row, html)
    html = FLEX_FORM.sub(repl_flex, html)

    def repl_plain(m: re.Match) -> str:
        val = m.group(0)
        if "list-filters-toolbar" in val or "align-items-end" in val:
            return val
        return _add_toolbar_class(val)

    html = ROW_FORM_PLAIN.sub(repl_plain, html)
    if "crm-customers-filter-toolbar" in html and "list-filters-toolbar" not in html.split("crm-customers-filter-toolbar")[1][:80]:
        html = html.replace(
            'class="crm-customers-filter-toolbar"',
            'class="list-filters-toolbar crm-customers-filter-toolbar"',
            1,
        )
    return html


def patch_buttons(html: str) -> str:
    html = FILTER_BTN.sub(
        r'<button type="submit" class="btn btn-primary btn-filter-icon\1" '
        r'title="Apply filters" aria-label="Apply filters">'
        r'<i class="fas fa-filter" aria-hidden="true"></i></button>',
        html,
    )
    html = APPLY_BTN_NO_ICON.sub(
        r'<button type="submit" class="btn btn-primary btn-filter-icon\1" '
        r'title="Apply filters" aria-label="Apply filters">'
        r'<i class="fas fa-filter" aria-hidden="true"></i></button>',
        html,
    )
    html = CLEAR_BTN.sub(
        r'<a href="\1" class="btn btn-light btn-filter-icon\2" '
        r'title="Clear filters" aria-label="Clear filters">'
        r'<i class="fas fa-times" aria-hidden="true"></i></a>',
        html,
    )
    # Text-only filter button with me-1 icon variants
    html = re.sub(
        r'<button type="submit" class="btn btn-primary([^"]*)">'
        r'\s*<i class="fas fa-filter([^"]*)"></i>\s*(Filter|Apply)\s*</button>',
        r'<button type="submit" class="btn btn-primary btn-filter-icon\1" '
        r'title="Apply filters" aria-label="Apply filters">'
        r'<i class="fas fa-filter\2" aria-hidden="true"></i></button>',
        html,
        flags=re.IGNORECASE,
    )
    html = re.sub(
        r'<a href="([^"]+)" class="btn btn-outline-secondary([^"]*)">\s*Clear\s*</a>',
        r'<a href="\1" class="btn btn-light btn-filter-icon\2" '
        r'title="Clear filters" aria-label="Clear filters">'
        r'<i class="fas fa-times" aria-hidden="true"></i></a>',
        html,
        flags=re.IGNORECASE,
    )
    return html


def patch_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if not any(
        x in text
        for x in (
            "fa-filter",
            "Filter</button>",
            "fa-search",
            "<!-- Filters -->",
            "list-filters-toolbar",
        )
    ):
        return False
    original = text
    if ROW_FORM.search(text) or FLEX_FORM.search(text) or "crm-customers-filter-toolbar" in text:
        text = patch_form_class(text)
    if "list-filters-toolbar" in text:
        text = LABEL_LINE.sub("", text)
        text = INLINE_LBL.sub("", text)
    text = patch_buttons(text)
    text = TEXT_FILTER_BTN.sub(
        r'<button type="submit" class="btn btn-primary btn-filter-icon \1" '
        r'title="Apply filters" aria-label="Apply filters">'
        r'<i class="fas fa-filter" aria-hidden="true"></i></button>',
        text,
    )
    text = SEARCH_BTN.sub(
        r'<button type="submit" class="btn btn-primary btn-filter-icon" '
        r'title="Search" aria-label="Search"><i class="fas fa-search" aria-hidden="true"></i></button>',
        text,
    )
    # Bank / finance outline filter row
    text = re.sub(
        r'<button type="submit" class="btn btn-outline-dark me-2">\s*'
        r'<i class="fas fa-filter me-1"></i>Filter\s*</button>',
        '<button type="submit" class="btn btn-primary btn-filter-icon" '
        'title="Apply filters" aria-label="Apply filters">'
        '<i class="fas fa-filter" aria-hidden="true"></i></button>',
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r'<a href="([^"]+)" class="btn btn-outline-secondary">\s*'
        r'<i class="fas fa-times me-1"></i>Clear\s*</a>',
        r'<a href="\1" class="btn btn-light btn-filter-icon" title="Clear filters" aria-label="Clear filters">'
        r'<i class="fas fa-times" aria-hidden="true"></i></a>',
        text,
        flags=re.IGNORECASE,
    )
    if "crm-customers-filter-toolbar" in text:
        text = re.sub(
            r"\.crm-customers-filter-toolbar \.form-label \{\s*margin-bottom:",
            ".crm-customers-filter-toolbar .form-label {\n    display: none !important;\n    margin-bottom:",
            text,
            count=1,
        )
        text = text.replace(
            '<div class="crm-filter-field crm-filter-actions">\n                '
            '<label class="form-label small text-muted d-none d-xl-block">&nbsp;</label>\n                ',
            '<div class="crm-filter-field crm-filter-actions filter-actions">\n                ',
        )
    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def main() -> None:
    changed = []
    for path in sorted(ROOT.rglob("*.html")):
        if patch_file(path):
            changed.append(path.relative_to(ROOT))
    print(f"Updated {len(changed)} templates")
    for p in changed:
        print(f"  {p}")


if __name__ == "__main__":
    main()
