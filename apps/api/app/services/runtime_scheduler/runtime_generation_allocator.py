from __future__ import annotations

from sqlalchemy import func, update
from sqlalchemy.orm import Session

from apps.api.app.models.scheduler_runtime_state import SchedulerRuntimeState


def allocate_next_runtime_generation(
    db: Session,
    *,
    scheduler_name: str,
) -> int:
    scheduler_name_value = str(scheduler_name or "").strip()

    if not scheduler_name_value:
        raise ValueError("scheduler_name_required")

    stmt = (
        update(SchedulerRuntimeState)
        .where(SchedulerRuntimeState.scheduler_name == scheduler_name_value)
        .where(SchedulerRuntimeState.last_runtime_generation >= 0)
        .values(
            last_runtime_generation=func.coalesce(
                SchedulerRuntimeState.last_runtime_generation,
                0,
            )
            + 1
        )
    )

    result = db.execute(stmt)

    if result.rowcount != 1:
        row = db.get(SchedulerRuntimeState, scheduler_name_value)
        if row is None:
            raise ValueError("scheduler_runtime_state_not_found")
        if row.last_runtime_generation is not None and row.last_runtime_generation < 0:
            raise ValueError("runtime_generation_must_not_be_negative")
        raise ValueError("runtime_generation_allocation_failed")

    row = db.get(SchedulerRuntimeState, scheduler_name_value)

    if row is None:
        raise ValueError("scheduler_runtime_state_not_found")

    db.refresh(row)

    return int(row.last_runtime_generation)
