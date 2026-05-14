from __future__ import annotations

from typing import Any


_BLOCK_REASONS = {
    "PROTECTED": "already_protected",
    "PARTIALLY_PROTECTED": "partial_protection_detected",
    "PROTECTION_UNKNOWN": "protection_state_unknown",
    "TRIGGERED": "triggered_requires_position_reconciliation",
}

_ALLOW_STATES = {"UNPROTECTED", "EXPIRED"}


def evaluate_protection_creation_gate(*, protection_state: str) -> dict[str, Any]:
    state = str(protection_state or "").upper().strip()

    if state in _ALLOW_STATES:
        return {
            "allow_creation": True,
            "protection_state": state,
            "reason": "eligible_for_creation",
        }

    return {
        "allow_creation": False,
        "protection_state": state,
        "reason": _BLOCK_REASONS.get(state, "protection_state_unknown"),
    }
