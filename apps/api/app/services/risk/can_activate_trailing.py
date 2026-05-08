from apps.api.app.services.risk.protection_decision import ProtectionDecision
from apps.api.app.services.risk.protection_reasons import (
    REASON_INVALID_CURRENT_STATE,
    REASON_OK,
    REASON_PROTECTION_NOT_VERIFIABLE,
)

STATE_AUTHORITATIVE_ACTIVE = "AUTHORITATIVE_ACTIVE"
STATE_TRAILING_READY = "TRAILING_READY"


def can_activate_trailing(
    *,
    current_state: str,
    protection_active_verifiable: bool,
) -> ProtectionDecision:
    state = str(current_state or "").strip()

    if state != STATE_AUTHORITATIVE_ACTIVE:
        return ProtectionDecision(
            allowed=False,
            reason=REASON_INVALID_CURRENT_STATE,
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
        next_state=STATE_TRAILING_READY,
    )
