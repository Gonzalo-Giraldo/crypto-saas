from apps.protection.constants import (
    STATE_AUTHORITATIVE_REPLACEMENT_PENDING,
    STATE_PROVISIONAL_CLEANUP_PENDING,
    REASON_OK,
    REASON_INVALID_CURRENT_STATE,
    REASON_PROTECTION_NOT_VERIFIABLE,
)

from apps.protection.protection_decision import ProtectionDecision


def can_start_cleanup(
    *,
    current_state: str,
    authoritative_sl_active: bool,
    authoritative_tp_active: bool,
    active_protection_verifiable: bool,
) -> ProtectionDecision:

    if current_state != STATE_AUTHORITATIVE_REPLACEMENT_PENDING:
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

    return ProtectionDecision(
        allowed=True,
        reason=REASON_OK,
        current_state=current_state,
        next_state=STATE_PROVISIONAL_CLEANUP_PENDING,
    )
