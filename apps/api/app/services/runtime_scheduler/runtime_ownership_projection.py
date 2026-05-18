from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from apps.api.app.models.scheduler_runtime_state import (
    SchedulerRuntimeState,
)
from apps.api.app.services.runtime_scheduler.runtime_stale_evaluator import (
    is_runtime_heartbeat_stale,
)


@dataclass(frozen=True)
class RuntimeOwnershipProjection:
    scheduler_name: str

    runtime_owner_id: str | None
    runtime_instance_id: str | None
    runtime_generation: int | None

    runtime_started_at: datetime | None
    runtime_heartbeat_at: datetime | None

    ownership_present: bool
    heartbeat_stale: bool

    runtime_locked: bool
    trading_enabled: bool
    dry_run: bool


def build_runtime_ownership_projection(
    *,
    runtime_state: SchedulerRuntimeState,
    now: datetime | None = None,
    stale_timeout_seconds: int = 60,
) -> RuntimeOwnershipProjection:
    ownership_present = bool(
        runtime_state.runtime_owner_id
        and runtime_state.runtime_instance_id
    )

    heartbeat_stale = is_runtime_heartbeat_stale(
        runtime_heartbeat_at=runtime_state.runtime_heartbeat_at,
        now=now,
        stale_timeout_seconds=stale_timeout_seconds,
    )

    return RuntimeOwnershipProjection(
        scheduler_name=runtime_state.scheduler_name,
        runtime_owner_id=runtime_state.runtime_owner_id,
        runtime_instance_id=runtime_state.runtime_instance_id,
        runtime_generation=runtime_state.runtime_generation,
        runtime_started_at=runtime_state.runtime_started_at,
        runtime_heartbeat_at=runtime_state.runtime_heartbeat_at,
        ownership_present=ownership_present,
        heartbeat_stale=heartbeat_stale,
        runtime_locked=runtime_state.runtime_locked,
        trading_enabled=runtime_state.trading_enabled,
        dry_run=runtime_state.dry_run,
    )
