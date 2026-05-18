from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from apps.api.app.models.scheduler_runtime_state import (
    SchedulerRuntimeState,
)
from apps.api.app.services.runtime_scheduler.runtime_ownership_validator import (
    validate_runtime_ownership_state,
)
from apps.api.app.services.runtime_scheduler.runtime_stale_evaluator import (
    is_runtime_heartbeat_stale,
)


class RuntimeOwnershipLifecycleState(StrEnum):
    INIT = "INIT"
    ACTIVE = "ACTIVE"
    STALE = "STALE"
    FAILED = "FAILED"


@dataclass(frozen=True)
class RuntimeOwnershipLifecycleProjection:
    state: RuntimeOwnershipLifecycleState
    valid_ownership: bool
    stale: bool
    operator_attention_required: bool
    reason: str | None


def build_runtime_ownership_lifecycle_projection(
    *,
    runtime_state: SchedulerRuntimeState,
    stale_after_seconds: int,
) -> RuntimeOwnershipLifecycleProjection:
    validation = validate_runtime_ownership_state(
        runtime_state=runtime_state,
    )

    if not validation.valid:
        return RuntimeOwnershipLifecycleProjection(
            state=RuntimeOwnershipLifecycleState.FAILED,
            valid_ownership=False,
            stale=True,
            operator_attention_required=True,
            reason=validation.reason,
        )

    ownership_present = runtime_state.runtime_owner_id is not None

    if not ownership_present:
        return RuntimeOwnershipLifecycleProjection(
            state=RuntimeOwnershipLifecycleState.INIT,
            valid_ownership=True,
            stale=False,
            operator_attention_required=False,
            reason="ownership_not_present",
        )

    stale = is_runtime_heartbeat_stale(
        runtime_heartbeat_at=runtime_state.runtime_heartbeat_at,
        stale_timeout_seconds=stale_after_seconds,
    )

    if stale:
        return RuntimeOwnershipLifecycleProjection(
            state=RuntimeOwnershipLifecycleState.STALE,
            valid_ownership=True,
            stale=True,
            operator_attention_required=True,
            reason="runtime_heartbeat_stale",
        )

    return RuntimeOwnershipLifecycleProjection(
        state=RuntimeOwnershipLifecycleState.ACTIVE,
        valid_ownership=True,
        stale=False,
        operator_attention_required=False,
        reason=None,
    )
