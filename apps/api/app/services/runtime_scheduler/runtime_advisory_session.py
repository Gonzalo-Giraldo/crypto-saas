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


@dataclass
class RuntimeAdvisorySession:
    acquired: bool = False
    connection_alive: bool = False
    lock_still_held: bool = False

    def current_state(self) -> RuntimeAdvisorySessionState:
        return evaluate_runtime_advisory_session(
            acquired=self.acquired,
            connection_alive=self.connection_alive,
            lock_still_held=self.lock_still_held,
        )

    def mark_acquired(self) -> None:
        self.acquired = True
        self.connection_alive = True
        self.lock_still_held = True

    def mark_connection_lost(self) -> None:
        self.connection_alive = False
        self.lock_still_held = False

    def mark_released(self) -> None:
        self.acquired = False
        self.connection_alive = False
        self.lock_still_held = False
