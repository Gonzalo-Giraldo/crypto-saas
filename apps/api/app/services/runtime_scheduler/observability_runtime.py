from __future__ import annotations

from apps.api.app.services.runtime_scheduler.runtime_state import (
    SchedulerRuntimeState,
)


def record_scheduler_tick_success_runtime(
    *,
    db,
    scheduler_name: str,
    runtime_state: SchedulerRuntimeState,
    duration_ms: int,
):
    raise NotImplementedError


def record_scheduler_tick_error_runtime(
    *,
    db,
    scheduler_name: str,
    runtime_state: SchedulerRuntimeState,
    duration_ms: int,
    error: str,
):
    raise NotImplementedError
