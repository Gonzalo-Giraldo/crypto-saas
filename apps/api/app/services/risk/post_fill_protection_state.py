from __future__ import annotations

from dataclasses import dataclass


PROVISIONAL_PENDING = "PROVISIONAL_PENDING"
PROVISIONAL_ACTIVE = "PROVISIONAL_ACTIVE"
AUTHORITATIVE_READY = "AUTHORITATIVE_READY"
CORRECTION_NOT_REQUIRED = "CORRECTION_NOT_REQUIRED"
CORRECTION_REQUIRED = "CORRECTION_REQUIRED"
AUTHORITATIVE_ACTIVE = "AUTHORITATIVE_ACTIVE"
CORRECTION_FAILED = "CORRECTION_FAILED"
TRAILING_READY = "TRAILING_READY"
TRAILING_ACTIVE = "TRAILING_ACTIVE"
PROTECTION_CRITICAL = "PROTECTION_CRITICAL"


_ALLOWED_TRANSITIONS = {
    (PROVISIONAL_PENDING, PROVISIONAL_ACTIVE),
    (PROVISIONAL_ACTIVE, AUTHORITATIVE_READY),
    (AUTHORITATIVE_READY, CORRECTION_NOT_REQUIRED),
    (AUTHORITATIVE_READY, CORRECTION_REQUIRED),
    (CORRECTION_NOT_REQUIRED, AUTHORITATIVE_ACTIVE),
    (CORRECTION_REQUIRED, AUTHORITATIVE_ACTIVE),
    (CORRECTION_REQUIRED, CORRECTION_FAILED),
    (AUTHORITATIVE_ACTIVE, TRAILING_READY),
    (TRAILING_READY, TRAILING_ACTIVE),
    (PROVISIONAL_PENDING, PROTECTION_CRITICAL),
    (PROVISIONAL_ACTIVE, PROTECTION_CRITICAL),
    (AUTHORITATIVE_READY, PROTECTION_CRITICAL),
    (CORRECTION_NOT_REQUIRED, PROTECTION_CRITICAL),
    (CORRECTION_REQUIRED, PROTECTION_CRITICAL),
    (AUTHORITATIVE_ACTIVE, PROTECTION_CRITICAL),
    (CORRECTION_FAILED, PROTECTION_CRITICAL),
    (TRAILING_READY, PROTECTION_CRITICAL),
    (TRAILING_ACTIVE, PROTECTION_CRITICAL),
}


@dataclass(frozen=True)
class ProtectionStateTransition:
    current_state: str
    next_state: str
    allowed: bool
    reason: str


def can_transition_protection_state(
    *,
    current_state: str,
    next_state: str,
) -> ProtectionStateTransition:
    """
    PURE FUNCTION.

    Protection state transition guard.
    NO DB.
    NO broker.
    NO runtime side effects.
    """

    current = str(current_state or "").upper().strip()
    nxt = str(next_state or "").upper().strip()

    if not current:
        return ProtectionStateTransition(
            current_state=current,
            next_state=nxt,
            allowed=False,
            reason="current_state_required",
        )

    if not nxt:
        return ProtectionStateTransition(
            current_state=current,
            next_state=nxt,
            allowed=False,
            reason="next_state_required",
        )

    allowed = (current, nxt) in _ALLOWED_TRANSITIONS

    return ProtectionStateTransition(
        current_state=current,
        next_state=nxt,
        allowed=allowed,
        reason="ok" if allowed else "transition_not_allowed",
    )
