from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.engine import Engine

from apps.api.app.services.runtime_scheduler.runtime_advisory_session import (
    RuntimeAdvisorySessionLock,
    RuntimeAdvisorySessionState,
)
from apps.api.app.services.runtime_scheduler.runtime_session_identity import (
    bind_runtime_advisory_session_state,
    clear_runtime_advisory_session_state,
)


@dataclass
class RuntimeAdvisorySessionAcquireResult:
    state: RuntimeAdvisorySessionState
    lock: RuntimeAdvisorySessionLock | None


def acquire_runtime_advisory_session(
    *,
    engine: Engine,
    scheduler_name: str,
) -> RuntimeAdvisorySessionAcquireResult:
    scheduler_name_value = str(scheduler_name or "").strip()

    if not scheduler_name_value:
        raise ValueError("scheduler_name_required")

    lock = RuntimeAdvisorySessionLock(
        engine=engine,
    )
    state = lock.acquire()

    bind_runtime_advisory_session_state(
        scheduler_name=scheduler_name_value,
        advisory_session_state=state,
    )

    if not state.valid:
        lock.release()
        clear_runtime_advisory_session_state(
            scheduler_name=scheduler_name_value,
        )
        return RuntimeAdvisorySessionAcquireResult(
            state=state,
            lock=None,
        )

    return RuntimeAdvisorySessionAcquireResult(
        state=state,
        lock=lock,
    )


def release_runtime_advisory_session(
    *,
    scheduler_name: str,
    lock: RuntimeAdvisorySessionLock | None,
) -> RuntimeAdvisorySessionState:
    scheduler_name_value = str(scheduler_name or "").strip()

    if not scheduler_name_value:
        raise ValueError("scheduler_name_required")

    if lock is None:
        state = clear_runtime_advisory_session_state(
            scheduler_name=scheduler_name_value,
        ).advisory_session_state
        return state

    state = lock.release()
    clear_runtime_advisory_session_state(
        scheduler_name=scheduler_name_value,
    )
    return state



def refresh_runtime_advisory_session_state(
    *,
    scheduler_name: str,
    lock: RuntimeAdvisorySessionLock | None,
) -> RuntimeAdvisorySessionState:
    scheduler_name_value = str(scheduler_name or "").strip()

    if not scheduler_name_value:
        raise ValueError("scheduler_name_required")

    if lock is None:
        return clear_runtime_advisory_session_state(
            scheduler_name=scheduler_name_value,
        ).advisory_session_state

    state = lock.current_state()

    if not state.valid:
        clear_runtime_advisory_session_state(
            scheduler_name=scheduler_name_value,
        )
        return state

    bind_runtime_advisory_session_state(
        scheduler_name=scheduler_name_value,
        advisory_session_state=state,
    )

    return state
