"""Post-save estimate edit workflow: revision bumps and re-approval."""
from dataclasses import dataclass

# Statuses where "Revise quotation" is available (after approval — not while awaiting approval).
REVISE_QUOTATION_STATUSES = frozenset({
    'approved',
    'under_negotiation',
    'rejected',
    'quotation_lost',
})

# Legacy aliases
REVISION_RESUBMIT_STATUSES = REVISE_QUOTATION_STATUSES
RESUBMIT_AFTER_EDIT_STATUSES = REVISION_RESUBMIT_STATUSES


@dataclass
class EstimateEditApplyResult:
    changed: bool = True
    resubmitted_for_approval: bool = False
    revision_bumped: bool = False
    edit_pending: bool = False


def _send_estimate_for_approval(request, estimate) -> None:
    estimate.status = 'sent'
    estimate.approval_requested_by = request.user
    estimate.awaiting_resubmit_revision = False
    estimate.edit_approval_status = 'none'
    estimate.edit_approval_submitted_at = None
    estimate.edit_approval_submitted_by_id = None


def apply_after_estimate_save(
    request,
    estimate,
    *,
    pre_status: str,
    pre_awaiting_resubmit_revision: bool = False,
    has_changes: bool = False,
    amount_affecting_changes: bool = False,
) -> EstimateEditApplyResult:
    """
    After a successful estimate save:
    - Revise mode + amount changes → revision bump (R1, R2, …) and sent for approval
    - Revise mode + basic edits only → save only; revision mode stays active
    - Normal edit (no Revise click) → save only
    """
    result = EstimateEditApplyResult(changed=True)

    if not pre_awaiting_resubmit_revision or not has_changes or not amount_affecting_changes:
        return result

    estimate.revision_count = (estimate.revision_count or 0) + 1
    update_fields = [
        'revision_count',
        'status',
        'approval_requested_by',
        'awaiting_resubmit_revision',
        'edit_approval_status',
        'edit_approval_submitted_at',
        'edit_approval_submitted_by',
        'updated_at',
    ]

    _send_estimate_for_approval(request, estimate)
    estimate.save(update_fields=update_fields)

    from .estimate_approval_notifications import notify_approver_estimate_sent

    notify_approver_estimate_sent(estimate, requested_by=request.user)
    result.resubmitted_for_approval = True
    result.revision_bumped = True
    return result
