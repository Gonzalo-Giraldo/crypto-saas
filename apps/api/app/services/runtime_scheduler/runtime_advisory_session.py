from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine


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



class RuntimeAdvisorySessionLock:
    """Dedicated PostgreSQL advisory session lock holder.

    Isolated primitive only. It does not grant execution authority by itself.
    """

    def __init__(
        self,
        *,
        engine: Engine,
        lock_key: int = AUTO_PICK_RUNTIME_SESSION_LOCK_KEY,
    ) -> None:
        self._engine = engine
        self._lock_key = int(lock_key)
        self._connection: Connection | None = None
        self._acquired = False

    def acquire(self) -> RuntimeAdvisorySessionState:
        if self._acquired:
            return self.current_state()

        connection = self._engine.connect()
        try:
            acquired = bool(
                connection.execute(
                    text("SELECT pg_try_advisory_lock(:lock_key)"),
                    {"lock_key": self._lock_key},
                ).scalar()
            )
        except Exception:
            connection.close()
            self._connection = None
            self._acquired = False
            return RuntimeAdvisorySessionState(False, False, "advisory_session_acquire_failed")

        if not acquired:
            connection.close()
            self._connection = None
            self._acquired = False
            return RuntimeAdvisorySessionState(False, False, "advisory_session_not_acquired")

        self._connection = connection
        self._acquired = True
        return self.current_state()

    def current_state(self) -> RuntimeAdvisorySessionState:
        if not self._acquired or self._connection is None:
            return evaluate_runtime_advisory_session(
                acquired=False,
                connection_alive=False,
                lock_still_held=False,
            )

        try:
            self._connection.execute(text("SELECT 1")).scalar()
        except Exception:
            self._mark_connection_lost()
            return evaluate_runtime_advisory_session(
                acquired=True,
                connection_alive=False,
                lock_still_held=False,
            )

        return evaluate_runtime_advisory_session(
            acquired=True,
            connection_alive=True,
            lock_still_held=True,
        )

    def release(self) -> RuntimeAdvisorySessionState:
        if self._connection is None:
            self._acquired = False
            return self.current_state()

        connection = self._connection
        try:
            if self._acquired:
                connection.execute(
                    text("SELECT pg_advisory_unlock(:lock_key)"),
                    {"lock_key": self._lock_key},
                ).scalar()
        except Exception:
            self._mark_connection_lost()
            return RuntimeAdvisorySessionState(True, False, "advisory_session_release_failed")
        finally:
            try:
                connection.close()
            finally:
                self._connection = None
                self._acquired = False

        return self.current_state()

    def _mark_connection_lost(self) -> None:
        connection = self._connection
        self._connection = None
        self._acquired = False
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass
