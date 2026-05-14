from __future__ import annotations

from typing import Any


def decide_protection_creation(
    *,
    allow_creation: bool,
    protection_state: str,
    reason: str,
) -> dict[str, Any]:
    state = str(protection_state or "").upper().strip()
    reason_norm = str(reason or "protection_state_unknown").strip()

    if allow_creation is True and state in {"UNPROTECTED", "EXPIRED"}:
        return {
            "proceed": True,
            "freeze_runtime": False,
            "protection_state": state,
            "reason": reason_norm,
        }

    return {
        "proceed": False,
        "freeze_runtime": True,
        "protection_state": state,
        "reason": reason_norm,
    }
