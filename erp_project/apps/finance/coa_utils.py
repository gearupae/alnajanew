"""Chart of Accounts hierarchy helpers."""
from __future__ import annotations

from apps.finance.models import Account


def _group_prefix(code: str) -> str:
    """Return the group prefix for a header account (1000 -> 10, 1410 -> 141)."""
    if len(code) >= 4 and code.endswith('00'):
        return code[:2]
    if code.endswith('0'):
        return code[:-1]
    return code


def infer_parent_code(code: str, existing_codes: set[str]) -> str | None:
    """
    Infer parent account code from numeric hierarchy.

    Examples:
        1010 -> 1000, 1101 -> 1100, 1411 -> 1410
    """
    if not code or len(code) < 2:
        return None

    best_match: str | None = None
    best_prefix_len = -1

    for candidate in existing_codes:
        if candidate == code or not candidate.endswith('0'):
            continue

        prefix = _group_prefix(candidate)
        if not prefix or not code.startswith(prefix) or code == candidate:
            continue

        if len(prefix) > best_prefix_len:
            best_match = candidate
            best_prefix_len = len(prefix)

    return best_match


def resolve_parent_accounts(accounts: list[Account]) -> dict[int, Account | None]:
    """Return account id -> parent Account (stored or inferred from code)."""
    by_code = {account.code: account for account in accounts}
    existing_codes = set(by_code.keys())
    resolved: dict[int, Account | None] = {}

    for account in accounts:
        if account.parent_id and account.parent:
            resolved[account.id] = account.parent
            continue
        parent_code = infer_parent_code(account.code, existing_codes)
        resolved[account.id] = by_code.get(parent_code) if parent_code else None

    return resolved


def link_account_parents(queryset=None, dry_run: bool = False) -> int:
    """Persist parent links inferred from account codes. Returns update count."""
    accounts = list((queryset or Account.objects.filter(is_active=True)).order_by('code'))
    by_code = {account.code: account for account in accounts}
    existing_codes = set(by_code.keys())
    updated = 0

    for account in accounts:
        parent_code = infer_parent_code(account.code, existing_codes)
        parent = by_code.get(parent_code) if parent_code else None
        new_parent_id = parent.id if parent else None
        if account.parent_id != new_parent_id:
            updated += 1
            if not dry_run:
                account.parent = parent
                account.save(update_fields=['parent'])

    return updated
