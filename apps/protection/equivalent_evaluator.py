from apps.protection.constants import (
    STATE_PROVISIONAL_ACTIVE,
    STATE_AUTHORITATIVE_ACTIVE_EQUIVALENT,
    REASON_EQUIVALENT_ACCEPTED,
    REASON_INVALID_CURRENT_STATE,
    REASON_RECONCILIATION_NOT_MATCHED,
    REASON_CORRECTION_REQUIRED,
    REASON_PROTECTION_NOT_VERIFIABLE,
)

from apps.protection.protection_decision import ProtectionDecision


def can_accept_authoritative_equivalent(
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

    if correction_required:
        return ProtectionDecision(
            allowed=False,
            reason=REASON_CORRECTION_REQUIRED,
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

    if not replacement_not_started:
        return ProtectionDecision(
            allowed=False,
            reason=REASON_INVALID_CURRENT_STATE,
            current_state=current_state,
            next_state=None,
        )

    return ProtectionDecision(
        allowed=True,
        reason=REASON_EQUIVALENT_ACCEPTED,
        current_state=current_state,
        next_state=STATE_AUTHORITATIVE_ACTIVE_EQUIVALENT,
    )
