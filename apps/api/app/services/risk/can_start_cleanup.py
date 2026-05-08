from apps.api.app.services.risk.protection_decision import (
    ProtectionDecision,
)
from apps.api.app.services.risk.protection_reasons import (
    REASON_AUTHORITATIVE_NOT_STABLE,
    REASON_INVALID_CURRENT_STATE,
    REASON_OK,
)

STATE_PROVISIONAL_CLEANUP_PENDING = (
    "PROVISIONAL_CLEANUP_PENDING"
)

STATE_AUTHORITATIVE_ACTIVE = "AUTHORITATIVE_ACTIVE"


def can_start_cleanup(
    *,
    current_state: str,
    authoritative_protection_stable: bool,
) -> ProtectionDecision:

    state = str(current_state or "").strip()

    if state != STATE_PROVISIONAL_CLEANUP_PENDING:
        return ProtectionDecision(
            allowed=False,
            reason=REASON_INVALID_CURRENT_STATE,
            current_state=state,
            next_state=None,
        )

    if not authoritative_protection_stable:
        return ProtectionDecision(
            allowed=False,
            reason=REASON_AUTHORITATIVE_NOT_STABLE,
            current_state=state,
            next_state=None,
        )

    return ProtectionDecision(
        allowed=True,
        reason=REASON_OK,
        current_state=state,
        next_state=STATE_AUTHORITATIVE_ACTIVE,
    )
