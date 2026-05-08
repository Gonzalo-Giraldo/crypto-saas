from apps.api.app.services.risk.protection_decision import ProtectionDecision
from apps.api.app.services.risk.protection_reasons import (
    REASON_CORRECTION_NOT_REQUIRED,
    REASON_INVALID_CURRENT_STATE,
    REASON_OK,
    REASON_PROTECTION_NOT_VERIFIABLE,
    REASON_RECONCILIATION_NOT_MATCHED,
)

STATE_PROVISIONAL_ACTIVE = "PROVISIONAL_ACTIVE"

STATE_AUTHORITATIVE_REPLACEMENT_PENDING = (
    "AUTHORITATIVE_REPLACEMENT_PENDING"
)


def can_start_replacement(
    *,
    current_state: str,
    reconciliation_status: str,
    correction_required: bool,
    protection_active_verifiable: bool,
) -> ProtectionDecision:

    state = str(current_state or "").strip()

    if state != STATE_PROVISIONAL_ACTIVE:
        return ProtectionDecision(
            allowed=False,
            reason=REASON_INVALID_CURRENT_STATE,
            current_state=state,
            next_state=None,
        )

    if str(reconciliation_status or "").strip().lower() != "matched":
        return ProtectionDecision(
            allowed=False,
            reason=REASON_RECONCILIATION_NOT_MATCHED,
            current_state=state,
            next_state=None,
        )

    if not correction_required:
        return ProtectionDecision(
            allowed=False,
            reason=REASON_CORRECTION_NOT_REQUIRED,
            current_state=state,
            next_state=None,
        )

    if not protection_active_verifiable:
        return ProtectionDecision(
            allowed=False,
            reason=REASON_PROTECTION_NOT_VERIFIABLE,
            current_state=state,
            next_state=None,
        )

    return ProtectionDecision(
        allowed=True,
        reason=REASON_OK,
        current_state=state,
        next_state=STATE_AUTHORITATIVE_REPLACEMENT_PENDING,
    )
