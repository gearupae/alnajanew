#!/usr/bin/env python3
"""Normalize *_detail.html overview blocks to project-detail markup (erp-entity-overview)."""
from __future__ import annotations

import re
import sys
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parents[1] / "templates"

COL_STD = "col-6 col-md-4 col-xl-3"
COL_FULL = "col-12"

HEADER_CLASS = "card-header bg-transparent py-3"

# Only top-level cards — not card-header / card-body / card-footer
CARD_OPEN_RE = re.compile(r'<div class="(card(?!-header|-body|-footer)[^"]*)"', re.I)


def col_replacement(col_class: str) -> str:
    c = col_class.strip()
    if "col-12" in c or "w-100" in c:
        return COL_FULL
    return COL_STD


TRAILING_IN_COL_RE = re.compile(
    r"(?:\s*(?:{%[^%]*%}\s*|<small\b[^>]*>.*?</small>|<p\b[^>]*>.*?</p>)\s*)*",
    re.DOTALL | re.IGNORECASE,
)


def convert_h6_field_block(m: re.Match) -> str:
    if "overview-label" in m.group(0):
        return m.group(0)
    col = col_replacement(m.group(1))
    label = m.group(2).strip()
    p_classes = (m.group(3) or "").strip()
    value_inner = m.group(4).strip()
    trailing = (m.group(5) or "").strip()
    if trailing:
        value_inner = f"{value_inner}\n{trailing}"
    value_class = ""
    if p_classes:
        parts = [x for x in p_classes.split() if x not in ("mb-0", "mb-1", "mb-2", "fw-medium")]
        if parts:
            value_class = " " + " ".join(parts)
    indent = m.group(0).split("\n")[0]
    pad = re.match(r"^(\s*)", m.group(0))
    sp = pad.group(1) if pad else "                    "
    return (
        f'{sp}<div class="{col}">\n'
        f"{sp}    <div class=\"overview-label\">{label}</div>\n"
        f'{sp}    <div class="overview-value{value_class}">{value_inner}</div>\n'
        f"{sp}</div>"
    )


H6_FIELD_RE = re.compile(
    r'<div class="((?:col-(?:\d+|sm-\d+|md-\d+|lg-\d+|xl-\d+)(?:\s+col-(?:\d+|sm-\d+|md-\d+|lg-\d+|xl-\d+))*|col))(?:\s+info-field)?">\s*'
    r'<h6 class="text-muted mb-2(?:\s+text-uppercase small fw-semibold|\s+small text-uppercase)?">\s*(.+?)\s*</h6>\s*'
    r'<p class="([^"]*)">(.*?)</p>\s*'
    r"((?:\s*(?:{%[^%]*%}\s*|<small\b[^>]*>.*?</small>|<p\b[^>]*>.*?</p>)\s*)*)"
    r"</div>",
    re.DOTALL | re.IGNORECASE,
)


def convert_info_field_block(m: re.Match) -> str:
    if "overview-label" in m.group(0):
        return m.group(0)
    col = col_replacement(m.group(1))
    label = re.sub(r"\s+", " ", m.group(2)).strip()
    p_classes = (m.group(3) or "").strip()
    value_inner = m.group(4).strip()
    if m.lastindex and m.lastindex >= 5:
        trailing = (m.group(5) or "").strip()
        if trailing:
            value_inner = f"{value_inner}\n{trailing}"
    value_class = ""
    if p_classes:
        parts = [x for x in p_classes.split() if x not in ("mb-0", "info-value", "fw-medium")]
        if parts:
            value_class = " " + " ".join(parts)
    pad = re.match(r"^(\s*)", m.group(0))
    sp = pad.group(1) if pad else "                    "
    return (
        f'{sp}<div class="{col}">\n'
        f"{sp}    <div class=\"overview-label\">{label}</div>\n"
        f'{sp}    <div class="overview-value{value_class}">{value_inner}</div>\n'
        f"{sp}</div>"
    )


INFO_FIELD_RE = re.compile(
    r'<div class="((?:col-(?:\d+|sm-\d+|md-\d+|lg-\d+|xl-\d+)(?:\s+col-(?:\d+|sm-\d+|md-\d+|lg-\d+|xl-\d+))*|col))(?:\s+info-field)?">\s*'
    r'<label class="form-label[^"]*info-label">([^<]+)</label>\s*'
    r'<p class="([^"]*)">(.*?)</p>\s*'
    r"((?:\s*(?:{%[^%]*%}\s*|<small\b[^>]*>.*?</small>|<p\b[^>]*>.*?</p>)\s*)*)"
    r"</div>",
    re.DOTALL | re.IGNORECASE,
)

FORM_LABEL_SMALL_RE = re.compile(
    r'<div class="((?:col-(?:\d+|sm-\d+|md-\d+|lg-\d+|xl-\d+)(?:\s+col-(?:\d+|sm-\d+|md-\d+|lg-\d+|xl-\d+))*|col))">\s*'
    r'<label class="form-label text-muted small">([^<]+)</label>\s*'
    r'<p class="([^"]*)">(.*?)</p>\s*'
    r"((?:\s*(?:{%[^%]*%}\s*|<small\b[^>]*>.*?</small>|<p\b[^>]*>.*?</p>|<a\b[^>]*>.*?</a>)\s*)*)"
    r"</div>",
    re.DOTALL | re.IGNORECASE,
)


def convert_erp_detail_field(m: re.Match) -> str:
    if "overview-label" in m.group(0):
        return m.group(0)
    full = "erp-detail-field-full" in m.group(0) or "erp-detail-field-span-2" in m.group(0)
    col = COL_FULL if full else COL_STD
    label = m.group(1).strip()
    p_classes = (m.group(2) or "").strip()
    value_inner = m.group(3).strip()
    value_class = ""
    if p_classes:
        parts = [x for x in p_classes.split() if x not in ("mb-0", "mb-1")]
        if parts:
            value_class = " " + " ".join(parts)
    pad = re.match(r"^(\s*)", m.group(0))
    sp = pad.group(1) if pad else "                    "
    return (
        f'{sp}<div class="{col}">\n'
        f"{sp}    <div class=\"overview-label\">{label}</div>\n"
        f'{sp}    <div class="overview-value{value_class}">{value_inner}</div>\n'
        f"{sp}</div>"
    )


ERP_DETAIL_FIELD_RE = re.compile(
    r'<div class="erp-detail-field(?:\s+erp-detail-field-(?:full|span-2))?">\s*'
    r"<h6>\s*(.+?)\s*</h6>\s*"
    r'<p(?:\s+class="([^"]*)")?>(.*?)</p>\s*</div>',
    re.DOTALL | re.IGNORECASE,
)


def erp_grid_to_row(text: str) -> str:
    def _repl_grid(m: re.Match) -> str:
        inner = m.group(1).strip()
        inner = ERP_DETAIL_FIELD_RE.sub(convert_erp_detail_field, inner)
        pad = re.match(r"^(\s*)", m.group(0))
        sp = pad.group(1) if pad else "                "
        return f'{sp}<div class="row g-3">\n{inner}\n{sp}</div>'

    return re.sub(
        r'<div class="erp-detail-grid">\s*(.*?)\s*</div>',
        _repl_grid,
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )


def card_has_overview_snippet(snippet: str) -> bool:
    return bool(
        re.search(
            r"(overview-label|erp-detail-grid|overview-section-title|"
            r'h6 class="text-muted mb-2|info-label|erp-detail-field|'
            r'label class="text-muted small d-block|table-borderless)',
            snippet,
            re.I,
        )
    )


def ensure_overview_card_class(text: str) -> str:
    parts: list[str] = []
    last = 0
    for m in CARD_OPEN_RE.finditer(text):
        parts.append(text[last : m.start()])
        classes = m.group(1)
        if "erp-entity-overview" in classes:
            parts.append(m.group(0))
        else:
            snippet = text[m.end() : m.end() + 3000]
            if card_has_overview_snippet(snippet):
                parts.append(f'<div class="{classes} erp-entity-overview"')
            else:
                parts.append(m.group(0))
        last = m.end()
    parts.append(text[last:])
    return "".join(parts)


def normalize_card_headers(text: str) -> str:
    out: list[str] = []
    last = 0
    for m in re.finditer(r'<div class="card-header[^"]*">', text):
        out.append(text[last : m.start()])
        before = text[max(0, m.start() - 500) : m.start()]
        if "erp-entity-overview" not in before:
            out.append(m.group(0))
        elif "bg-transparent" in m.group(0):
            out.append(m.group(0))
        else:
            out.append(f'<div class="{HEADER_CLASS}">')
        last = m.end()
    out.append(text[last:])
    return "".join(out)


def normalize_overview_rows(text: str) -> str:
    """Within erp-entity-overview cards, prefer g-3 for direct field rows."""

    def _fix_row_g4(m: re.Match) -> str:
        before = text[max(0, m.start() - 800) : m.start()]
        after = text[m.end() : m.end() + 200]
        if "erp-entity-overview" not in before:
            return m.group(0)
        if "overview-label" in after or "overview-section-title" in after or "h6 class=\"text-muted" in after:
            return '<div class="row g-3">'
        return m.group(0)

    return re.sub(r'<div class="row g-4">', _fix_row_g4, text)


def process_file(path: Path, dry_run: bool = False) -> bool:
    original = path.read_text(encoding="utf-8")
    text = original
    text = ensure_overview_card_class(text)
    text = erp_grid_to_row(text)
    text = ERP_DETAIL_FIELD_RE.sub(convert_erp_detail_field, text)
    for _ in range(8):
        new = INFO_FIELD_RE.sub(convert_info_field_block, text)
        new = FORM_LABEL_SMALL_RE.sub(convert_info_field_block, new)
        new = H6_FIELD_RE.sub(convert_h6_field_block, new)
        if new == text:
            break
        text = new
    text = normalize_overview_rows(text)
    text = normalize_card_headers(text)
    if text == original:
        return False
    if not dry_run:
        path.write_text(text, encoding="utf-8")
    return True


def main() -> int:
    dry = "--dry-run" in sys.argv
    changed = 0
    for path in sorted(TEMPLATES.rglob("*detail*.html")):
        if process_file(path, dry_run=dry):
            changed += 1
            print(path.relative_to(TEMPLATES.parent))
    print(f"{'Would update' if dry else 'Updated'} {changed} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
