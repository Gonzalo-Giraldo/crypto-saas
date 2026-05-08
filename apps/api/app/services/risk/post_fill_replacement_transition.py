from __future__ import annotations

from dataclasses import dataclass

from apps.api.app.services.risk.post_fill_protection_state import (
    AUTHORITATIVE_ACTIVE,
    CORRECTION_FAILED,
    CORRECTION_REQUIRED,
    PROTECTION_CRITICAL,
    TRAILING_READY,
    can_transition_protection_state,
)


AUTHORITATIVE_CREATE_CONFIRMED = "AUTHORITATIVE_CREATE_CONFIRMED"
AUTHORITATIVE_CREATE_FAILED = "AUTHORITATIVE_CREATE_FAILED"
PROVISIONAL_CANCEL_CONFIRMED = "PROVISIONAL_CANCEL_CONFIRMED"
PROVISIONAL_CANCEL_FAILED = "PROVISIONAL_CANCEL_FAILED"
TRAILING_TAKEOVER_READY = "TRAILING_TAKEOVER_READY"
REPLACEMENT_CRITICAL_FAILURE = "REPLACEMENT_CRITICAL_FAILURE"


@dataclass(frozen=True)
class ReplacementTransitionDecision:
    current_state: str
    event: str
    next_state: str
    allowed: bool
    reason: str


def decide_replacement_transition(
    *,
    current_state: str,
    event: str,
) -> ReplacementTransitionDecision:
    """
    PURE FUNCTION.

    Models safe replacement transition semantics only.
    NO DB.
    NO broker.
    NO runtime side effects.
    """

    current = str(current_state or "").upper().strip()
    evt = str(event or "").upper().strip()

    if not current:
        return ReplacementTransitionDecision(
            current_state=current,
            event=evt,
            next_state="",
            allowed=False,
            reason="current_state_required",
        )

    if not evt:
        return ReplacementTransitionDecision(
            current_state=current,
            event=evt,
            next_state="",
            allowed=False,
            reason="event_required",
        )

    if current != CORRECTION_REQUIRED and evt in {
        AUTHORITATIVE_CREATE_CONFIRMED,
        AUTHORITATIVE_CREATE_FAILED,
    }:
        return ReplacementTransitionDecision(
            current_state=current,
            event=evt,
            next_state=current,
            allowed=False,
            reason="event_requires_correction_required",
        )

    if evt == AUTHORITATIVE_CREATE_CONFIRMED:
        next_state = AUTHORITATIVE_ACTIVE
    elif evt == AUTHORITATIVE_CREATE_FAILED:
        next_state = CORRECTION_FAILED
    elif evt == PROVISIONAL_CANCEL_CONFIRMED:
        next_state = TRAILING_READY
    elif evt == PROVISIONAL_CANCEL_FAILED:
        next_state = AUTHORITATIVE_ACTIVE
    elif evt == TRAILING_TAKEOVER_READY:
        next_state = TRAILING_READY
    elif evt == REPLACEMENT_CRITICAL_FAILURE:
        next_state = PROTECTION_CRITICAL
    else:
        return ReplacementTransitionDecision(
            current_state=current,
            event=evt,
            next_state=current,
            allowed=False,
            reason="unknown_replacement_event",
        )

    transition = can_transition_protection_state(
        current_state=current,
        next_state=next_state,
    )

    return ReplacementTransitionDecision(
        current_state=current,
        event=evt,
        next_state=next_state,
        allowed=transition.allowed,
        reason=transition.reason,
    )
