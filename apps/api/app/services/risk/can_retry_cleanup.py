from apps.api.app.services.risk.protection_decision import (
    ProtectionDecision,
)
from apps.api.app.services.risk.protection_reasons import (
    REASON_INVALID_CURRENT_STATE,
    REASON_OK,
    REASON_PROTECTION_NOT_VERIFIABLE,
)

STATE_STALE_PROVISIONAL_PRESENT = (
    "STALE_PROVISIONAL_PRESENT"
)

STATE_PROVISIONAL_CLEANUP_PENDING = (
    "PROVISIONAL_CLEANUP_PENDING"
)


def can_retry_cleanup(
    *,
    current_state: str,
    protection_active_verifiable: bool,
) -> ProtectionDecision:

    state = str(current_state or "").strip()

    if state != STATE_STALE_PROVISIONAL_PRESENT:
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
        next_state=STATE_PROVISIONAL_CLEANUP_PENDING,
    )
