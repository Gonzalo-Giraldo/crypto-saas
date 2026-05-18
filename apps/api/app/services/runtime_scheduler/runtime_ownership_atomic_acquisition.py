from __future__ import annotations

from datetime import datetime

from sqlalchemy import update
from sqlalchemy.orm import Session

from apps.api.app.models.scheduler_runtime_state import (
    SchedulerRuntimeState,
)


def atomic_acquire_runtime_ownership(
    db: Session,
    *,
    scheduler_name: str,
    runtime_owner_id: str,
    runtime_instance_id: str,
    runtime_generation: int,
    now: datetime,
) -> bool:
    scheduler_name_value = str(scheduler_name or "").strip()
    runtime_owner_id_value = str(runtime_owner_id or "").strip()
    runtime_instance_id_value = str(runtime_instance_id or "").strip()

    if not scheduler_name_value:
        raise ValueError("scheduler_name_required")

    if not runtime_owner_id_value:
        raise ValueError("runtime_owner_id_required")

    if not runtime_instance_id_value:
        raise ValueError("runtime_instance_id_required")

    if runtime_generation <= 0:
        raise ValueError("runtime_generation_must_be_positive")

    if now.tzinfo is None:
        raise ValueError("now_must_be_timezone_aware")

    stmt = (
        update(SchedulerRuntimeState)
        .where(
            SchedulerRuntimeState.scheduler_name == scheduler_name_value,
        )
        .where(
            SchedulerRuntimeState.runtime_owner_id.is_(None),
        )
        .where(
            SchedulerRuntimeState.runtime_instance_id.is_(None),
        )
        .where(
            SchedulerRuntimeState.runtime_generation.is_(None),
        )
        .where(
            SchedulerRuntimeState.runtime_started_at.is_(None),
        )
        .where(
            SchedulerRuntimeState.runtime_heartbeat_at.is_(None),
        )
        .values(
            runtime_owner_id=runtime_owner_id_value,
            runtime_instance_id=runtime_instance_id_value,
            runtime_generation=runtime_generation,
            runtime_started_at=now,
            runtime_heartbeat_at=now,
        )
    )

    result = db.execute(stmt)

    return result.rowcount == 1
