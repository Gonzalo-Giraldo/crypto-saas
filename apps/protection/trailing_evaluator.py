from apps.protection.constants import (
    STATE_AUTHORITATIVE_ACTIVE,
    STATE_AUTHORITATIVE_ACTIVE_EQUIVALENT,
    STATE_TRAILING_READY,
    REASON_OK,
    REASON_INVALID_CURRENT_STATE,
    REASON_AUTHORITATIVE_NOT_STABLE,
    REASON_PROTECTION_NOT_VERIFIABLE,
)

from apps.protection.protection_decision import ProtectionDecision


VALID_TRAILING_SOURCE_STATES = {
    STATE_AUTHORITATIVE_ACTIVE,
    STATE_AUTHORITATIVE_ACTIVE_EQUIVALENT,
}


def can_activate_trailing(
    *,
    current_state: str,
    baseline_stable: bool,
    active_protection_verifiable: bool,
    authoritative_sl_active: bool,
    authoritative_tp_active: bool,
    trailing_not_active: bool,
) -> ProtectionDecision:

    if current_state not in VALID_TRAILING_SOURCE_STATES:
        return ProtectionDecision(
            allowed=False,
            reason=REASON_INVALID_CURRENT_STATE,
            current_state=current_state,
            next_state=None,
        )

    if not baseline_stable:
        return ProtectionDecision(
            allowed=False,
            reason=REASON_AUTHORITATIVE_NOT_STABLE,
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

    if not trailing_not_active:
        return ProtectionDecision(
            allowed=False,
            reason=REASON_INVALID_CURRENT_STATE,
            current_state=current_state,
            next_state=None,
        )

    return ProtectionDecision(
        allowed=True,
        reason=REASON_OK,
        current_state=current_state,
        next_state=STATE_TRAILING_READY,
    )
