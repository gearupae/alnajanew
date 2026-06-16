"""Group project item lines by source quotation for display."""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal


def build_project_item_sections(item_lines):
    """
    Split item lines into ordered sections (one per source estimate / legacy bucket).

    Returns list of dicts:
      label, estimate, lines, subtotal_net, subtotal_vat, subtotal_incl_vat, spacer_before
    """
    buckets: dict[int | None, list] = defaultdict(list)
    for line in item_lines:
        buckets[getattr(line, 'source_estimate_id', None)].append(line)

    def _section_sort_key(est_id):
        lines = buckets[est_id]
        return min((ln.sort_order, ln.pk) for ln in lines)

    ordered_ids = sorted(buckets.keys(), key=_section_sort_key)
    sections = []
    for idx, est_id in enumerate(ordered_ids):
        lines = sorted(buckets[est_id], key=lambda ln: (ln.sort_order, ln.pk))
        estimate = None
        if est_id and lines:
            estimate = getattr(lines[0], 'source_estimate', None)
        if estimate:
            number = getattr(estimate, 'display_estimate_number', None) or estimate.estimate_number
            label = f'Quotation {number}'
        elif est_id is None:
            label = 'Project items'
        else:
            label = 'Project items'

        subtotal_net = sum((ln.line_net or Decimal('0')) for ln in lines)
        subtotal_vat = sum((ln.vat_amount or Decimal('0')) for ln in lines)
        sections.append(
            {
                'key': est_id or 'legacy',
                'label': label,
                'estimate': estimate,
                'lines': lines,
                'subtotal_net': subtotal_net,
                'subtotal_vat': subtotal_vat,
                'subtotal_incl_vat': subtotal_net + subtotal_vat,
                'spacer_before': idx > 0,
            }
        )
    return sections
