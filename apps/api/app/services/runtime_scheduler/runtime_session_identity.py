from __future__ import annotations

from dataclasses import dataclass

from apps.api.app.services.runtime_scheduler.runtime_advisory_session import (
    RuntimeAdvisorySessionState,
    evaluate_runtime_advisory_session,
)
from apps.api.app.services.runtime_scheduler.runtime_identity import (
    build_runtime_instance_id,
    build_runtime_owner_id,
)


@dataclass(frozen=True)
class RuntimeSessionIdentity:
    scheduler_name: str
    runtime_owner_id: str
    runtime_instance_id: str


@dataclass
class RuntimeSessionLocalState:
    identity: RuntimeSessionIdentity
    runtime_generation: int | None = None
    advisory_session_state: RuntimeAdvisorySessionState = evaluate_runtime_advisory_session(
        acquired=False,
        connection_alive=False,
        lock_still_held=False,
    )


_runtime_session_identities: dict[str, RuntimeSessionIdentity] = {}
_runtime_session_local_states: dict[str, RuntimeSessionLocalState] = {}


def get_runtime_session_identity(
    *,
    scheduler_name: str,
) -> RuntimeSessionIdentity:
    scheduler_value = str(scheduler_name or "").strip()

    if not scheduler_value:
        raise ValueError("scheduler_name_required")

    existing = _runtime_session_identities.get(scheduler_value)

    if existing is not None:
        return existing

    identity = RuntimeSessionIdentity(
        scheduler_name=scheduler_value,
        runtime_owner_id=build_runtime_owner_id(
            scheduler_name=scheduler_value,
        ),
        runtime_instance_id=build_runtime_instance_id(
            scheduler_name=scheduler_value,
        ),
    )

    _runtime_session_identities[scheduler_value] = identity

    return identity



def get_runtime_session_local_state(
    *,
    scheduler_name: str,
) -> RuntimeSessionLocalState:
    identity = get_runtime_session_identity(
        scheduler_name=scheduler_name,
    )

    existing = _runtime_session_local_states.get(identity.scheduler_name)

    if existing is not None:
        return existing

    state = RuntimeSessionLocalState(
        identity=identity,
    )

    _runtime_session_local_states[identity.scheduler_name] = state

    return state


def bind_runtime_session_generation(
    *,
    scheduler_name: str,
    runtime_generation: int,
) -> RuntimeSessionLocalState:
    if runtime_generation <= 0:
        raise ValueError("runtime_generation_must_be_positive")

    state = get_runtime_session_local_state(
        scheduler_name=scheduler_name,
    )

    state.runtime_generation = runtime_generation

    return state


def clear_runtime_session_generation(
    *,
    scheduler_name: str,
) -> RuntimeSessionLocalState:
    state = get_runtime_session_local_state(
        scheduler_name=scheduler_name,
    )

    state.runtime_generation = None

    return state



def bind_runtime_advisory_session_state(
    *,
    scheduler_name: str,
    advisory_session_state: RuntimeAdvisorySessionState,
) -> RuntimeSessionLocalState:
    state = get_runtime_session_local_state(
        scheduler_name=scheduler_name,
    )

    state.advisory_session_state = advisory_session_state

    return state


def clear_runtime_advisory_session_state(
    *,
    scheduler_name: str,
) -> RuntimeSessionLocalState:
    state = get_runtime_session_local_state(
        scheduler_name=scheduler_name,
    )

    state.advisory_session_state = evaluate_runtime_advisory_session(
        acquired=False,
        connection_alive=False,
        lock_still_held=False,
    )

    return state
