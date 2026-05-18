from __future__ import annotations

import time
from datetime import datetime, timezone

from apps.api.app.services.runtime_scheduler.contracts import (
    SchedulerTickContext,
)


def build_scheduler_tick_context(
    *,
    scheduler_name: str,
    dry_run: bool | None = None,
    trading_enabled: bool | None = None,
    execution_mode: str | None = None,
) -> SchedulerTickContext:
    return SchedulerTickContext(
        scheduler_name=scheduler_name,
        started_monotonic=time.monotonic(),
        started_at_wall=datetime.now(timezone.utc),
        dry_run=dry_run,
        trading_enabled=trading_enabled,
        execution_mode=execution_mode,
    )
