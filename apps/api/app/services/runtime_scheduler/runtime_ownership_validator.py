from __future__ import annotations

from dataclasses import dataclass

from apps.api.app.models.scheduler_runtime_state import (
    SchedulerRuntimeState,
)


@dataclass(frozen=True)
class RuntimeOwnershipValidationResult:
    valid: bool
    reason: str | None


def validate_runtime_ownership_state(
    *,
    runtime_state: SchedulerRuntimeState,
) -> RuntimeOwnershipValidationResult:
    owner_present = bool(runtime_state.runtime_owner_id)
    instance_present = bool(runtime_state.runtime_instance_id)
    generation_present = runtime_state.runtime_generation is not None
    heartbeat_present = (
        runtime_state.runtime_heartbeat_at is not None
    )

    ownership_fields = [
        owner_present,
        instance_present,
        generation_present,
        heartbeat_present,
    ]

    partially_present = any(ownership_fields) and not all(
        ownership_fields
    )

    if partially_present:
        return RuntimeOwnershipValidationResult(
            valid=False,
            reason="partial_ownership_state",
        )

    if generation_present and runtime_state.runtime_generation <= 0:
        return RuntimeOwnershipValidationResult(
            valid=False,
            reason="invalid_runtime_generation",
        )

    return RuntimeOwnershipValidationResult(
        valid=True,
        reason=None,
    )
