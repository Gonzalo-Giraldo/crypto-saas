from apps.protection.constants import (
    REASON_INVALID_CURRENT_STATE,
)

from apps.protection.protection_decision import ProtectionDecision
from apps.protection.transition_registry import ALLOWED_TRANSITIONS


def is_allowed_transition(
    *,
    current_state: str,
    next_state: str,
) -> bool:
    return next_state in ALLOWED_TRANSITIONS.get(current_state, set())


def assert_allowed_transition(
    *,
    current_state: str,
    next_state: str,
) -> ProtectionDecision:
    if is_allowed_transition(
        current_state=current_state,
        next_state=next_state,
    ):
        return ProtectionDecision(
            allowed=True,
            reason="REASON_OK",
            current_state=current_state,
            next_state=next_state,
        )

    return ProtectionDecision(
        allowed=False,
        reason=REASON_INVALID_CURRENT_STATE,
        current_state=current_state,
        next_state=None,
    )
