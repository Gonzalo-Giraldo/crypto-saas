from apps.api.app.services.risk.protection_decision import (
    ProtectionDecision,
)
from apps.api.app.services.risk.protection_reasons import (
    REASON_OK,
    REASON_PROTECTION_NOT_VERIFIABLE,
)

STATE_PROTECTION_CRITICAL = "PROTECTION_CRITICAL"


def evaluate_protection_critical(
    *,
    current_state: str,
    protection_active_verifiable: bool,
) -> ProtectionDecision:

    state = str(current_state or "").strip()

    if protection_active_verifiable:
        return ProtectionDecision(
            allowed=True,
            reason=REASON_OK,
            current_state=state,
            next_state=None,
        )

    return ProtectionDecision(
        allowed=False,
        reason=REASON_PROTECTION_NOT_VERIFIABLE,
        current_state=STATE_PROTECTION_CRITICAL,
        next_state=STATE_PROTECTION_CRITICAL,
    )
