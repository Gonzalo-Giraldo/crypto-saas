from __future__ import annotations

from dataclasses import dataclass


AUTO_PICK_RUNTIME_SESSION_LOCK_KEY = 887732


@dataclass(frozen=True)
class RuntimeAdvisorySessionState:
    acquired: bool
    valid: bool
    reason: str | None


def evaluate_runtime_advisory_session(
    *,
    acquired: bool,
    connection_alive: bool,
    lock_still_held: bool,
) -> RuntimeAdvisorySessionState:
    if not acquired:
        return RuntimeAdvisorySessionState(False, False, "advisory_session_not_acquired")

    if not connection_alive:
        return RuntimeAdvisorySessionState(True, False, "advisory_session_connection_lost")

    if not lock_still_held:
        return RuntimeAdvisorySessionState(True, False, "advisory_session_lock_lost")

    return RuntimeAdvisorySessionState(True, True, None)
