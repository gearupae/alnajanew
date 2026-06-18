"""Post-save estimate edit workflow: re-approval and revision bumps."""
from dataclasses import dataclass

# Statuses where the user may click "Revise quotation" before saving a new R1/R2…
REVISE_QUOTATION_STATUSES = frozenset({
    'sent',
    'approved',
    'under_negotiation',
    'rejected',
    'quotation_lost',
})

# Legacy alias — revision bumps now require awaiting_resubmit_revision for all statuses.
REVISION_RESUBMIT_STATUSES = REVISE_QUOTATION_STATUSES
RESUBMIT_AFTER_EDIT_STATUSES = REVISION_RESUBMIT_STATUSES


@dataclass
class EstimateEditApplyResult:
    changed: bool = True
    resubmitted_for_approval: bool = False
    revision_bumped: bool = False
    edit_pending: bool = False


def apply_after_estimate_save(
    request,
    estimate,
    *,
    pre_status: str,
    pre_awaiting_resubmit_revision: bool = False,
) -> EstimateEditApplyResult:
    """
    After a successful estimate save with detected changes:
    - Any status → revision bump + sent only when Revise quotation was requested
    - draft → no approval action
    """
    result = EstimateEditApplyResult(changed=True)

    should_resubmit = pre_awaiting_resubmit_revision
    if should_resubmit:
        estimate.revision_count = (estimate.revision_count or 0) + 1
        estimate.status = 'sent'
        estimate.approval_requested_by = request.user
        estimate.awaiting_resubmit_revision = False
        estimate.edit_approval_status = 'none'
        estimate.edit_approval_submitted_at = None
        estimate.edit_approval_submitted_by_id = None
        estimate.save(
            update_fields=[
                'revision_count',
                'status',
                'approval_requested_by',
                'awaiting_resubmit_revision',
                'edit_approval_status',
                'edit_approval_submitted_at',
                'edit_approval_submitted_by',
                'updated_at',
            ]
        )
        from .estimate_approval_notifications import notify_approver_estimate_sent

        notify_approver_estimate_sent(estimate, requested_by=request.user)
        result.resubmitted_for_approval = True
        result.revision_bumped = True
        return result

    return result
