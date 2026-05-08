from apps.protection.constants import (
    STATE_PROVISIONAL_ACTIVE,
    STATE_AUTHORITATIVE_REPLACEMENT_PENDING,
    REASON_OK,
    REASON_INVALID_CURRENT_STATE,
    REASON_RECONCILIATION_NOT_MATCHED,
    REASON_CORRECTION_NOT_REQUIRED,
    REASON_PROTECTION_NOT_VERIFIABLE,
)

from apps.protection.protection_decision import ProtectionDecision


def can_start_authoritative_replacement(
    *,
    current_state: str,
    reconciliation_status: str,
    safe_for_position_update: bool,
    correction_required: bool,
    provisional_sl_active: bool,
    provisional_tp_active: bool,
    active_protection_verifiable: bool,
    replacement_not_started: bool,
) -> ProtectionDecision:

    if current_state != STATE_PROVISIONAL_ACTIVE:
        return ProtectionDecision(
            allowed=False,
            reason=REASON_INVALID_CURRENT_STATE,
            current_state=current_state,
            next_state=None,
        )

    if reconciliation_status != "matched":
        return ProtectionDecision(
            allowed=False,
            reason=REASON_RECONCILIATION_NOT_MATCHED,
            current_state=current_state,
            next_state=None,
        )

    if not safe_for_position_update:
        return ProtectionDecision(
            allowed=False,
            reason=REASON_RECONCILIATION_NOT_MATCHED,
            current_state=current_state,
            next_state=None,
        )

    if not correction_required:
        return ProtectionDecision(
            allowed=False,
            reason=REASON_CORRECTION_NOT_REQUIRED,
            current_state=current_state,
            next_state=None,
        )

    if not replacement_not_started:
        return ProtectionDecision(
            allowed=False,
            reason=REASON_INVALID_CURRENT_STATE,
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

    if not provisional_sl_active or not provisional_tp_active:
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
        next_state=STATE_AUTHORITATIVE_REPLACEMENT_PENDING,
    )
