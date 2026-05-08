from apps.protection.constants import (
    STATE_PROVISIONAL_CLEANUP_PENDING,
    STATE_AUTHORITATIVE_ACTIVE,
    STATE_STALE_PROVISIONAL_PRESENT,
    REASON_OK,
    REASON_INVALID_CURRENT_STATE,
    REASON_PROTECTION_NOT_VERIFIABLE,
)

from apps.protection.protection_decision import ProtectionDecision


def evaluate_cleanup_result(
    *,
    current_state: str,
    cleanup_successful: bool,
    stale_provisional_present: bool,
    authoritative_sl_active: bool,
    authoritative_tp_active: bool,
    active_protection_verifiable: bool,
) -> ProtectionDecision:

    if current_state != STATE_PROVISIONAL_CLEANUP_PENDING:
        return ProtectionDecision(
            allowed=False,
            reason=REASON_INVALID_CURRENT_STATE,
            current_state=current_state,
            next_state=None,
        )

    if not authoritative_sl_active or not authoritative_tp_active:
        return ProtectionDecision(
            allowed=False,
            reason=REASON_PROTECTION_NOT_VERIFIABLE,
            current_state=current_state,
            next_state=None,
        )

    if not active_protection_verifiable:
        return ProtectionDecision(
            allowed=False,
            reason=REASON_PROTECTION_NOT_VERIFIABLE,
            current_state=current_state,
            next_state=None,
        )

    if cleanup_successful and not stale_provisional_present:
        return ProtectionDecision(
            allowed=True,
            reason=REASON_OK,
            current_state=current_state,
            next_state=STATE_AUTHORITATIVE_ACTIVE,
        )

    if not cleanup_successful and stale_provisional_present:
        return ProtectionDecision(
            allowed=True,
            reason=REASON_OK,
            current_state=current_state,
            next_state=STATE_STALE_PROVISIONAL_PRESENT,
        )

    return ProtectionDecision(
        allowed=False,
        reason=REASON_INVALID_CURRENT_STATE,
        current_state=current_state,
        next_state=None,
    )
