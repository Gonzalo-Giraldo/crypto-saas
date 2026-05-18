from __future__ import annotations

from dataclasses import dataclass

from apps.api.app.services.runtime_scheduler.runtime_identity import (
    build_runtime_instance_id,
    build_runtime_owner_id,
)


@dataclass(frozen=True)
class RuntimeSessionIdentity:
    scheduler_name: str
    runtime_owner_id: str
    runtime_instance_id: str


_runtime_session_identities: dict[str, RuntimeSessionIdentity] = {}


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
