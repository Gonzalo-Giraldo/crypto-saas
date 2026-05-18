from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from apps.api.app.models.scheduler_runtime_state import (
    SchedulerRuntimeState,
)
from apps.api.app.services.runtime_scheduler.runtime_identity import (
    build_runtime_instance_id,
    build_runtime_owner_id,
)
from apps.api.app.services.runtime_scheduler.runtime_ownership_atomic_acquisition import (
    atomic_acquire_runtime_ownership,
)
from apps.api.app.services.runtime_scheduler.runtime_ownership_validator import (
    validate_runtime_ownership_state,
)


@dataclass(frozen=True)
class RuntimeOwnershipAcquireResult:
    acquired: bool

    scheduler_name: str

    runtime_owner_id: str | None
    runtime_instance_id: str | None
    runtime_generation: int | None

    reason: str | None


def acquire_runtime_ownership(
    db: Session,
    *,
    runtime_state: SchedulerRuntimeState,
    now: datetime,
) -> RuntimeOwnershipAcquireResult:
    validation = validate_runtime_ownership_state(
        runtime_state=runtime_state,
    )

    if not validation.valid:
        return RuntimeOwnershipAcquireResult(
            acquired=False,
            scheduler_name=runtime_state.scheduler_name,
            runtime_owner_id=runtime_state.runtime_owner_id,
            runtime_instance_id=runtime_state.runtime_instance_id,
            runtime_generation=runtime_state.runtime_generation,
            reason=validation.reason,
        )

    ownership_present = (
        runtime_state.runtime_owner_id is not None
    )

    if ownership_present:
        return RuntimeOwnershipAcquireResult(
            acquired=False,
            scheduler_name=runtime_state.scheduler_name,
            runtime_owner_id=runtime_state.runtime_owner_id,
            runtime_instance_id=runtime_state.runtime_instance_id,
            runtime_generation=runtime_state.runtime_generation,
            reason="ownership_already_present",
        )

    runtime_owner_id = build_runtime_owner_id(
        scheduler_name=runtime_state.scheduler_name,
    )

    runtime_instance_id = build_runtime_instance_id(
        scheduler_name=runtime_state.scheduler_name,
    )

    runtime_generation = 1

    acquired = atomic_acquire_runtime_ownership(
        db,
        scheduler_name=runtime_state.scheduler_name,
        runtime_owner_id=runtime_owner_id,
        runtime_instance_id=runtime_instance_id,
        runtime_generation=runtime_generation,
        now=now,
    )

    if not acquired:
        return RuntimeOwnershipAcquireResult(
            acquired=False,
            scheduler_name=runtime_state.scheduler_name,
            runtime_owner_id=None,
            runtime_instance_id=None,
            runtime_generation=None,
            reason="atomic_acquisition_failed",
        )

    return RuntimeOwnershipAcquireResult(
        acquired=True,
        scheduler_name=runtime_state.scheduler_name,
        runtime_owner_id=runtime_owner_id,
        runtime_instance_id=runtime_instance_id,
        runtime_generation=runtime_generation,
        reason=None,
    )
