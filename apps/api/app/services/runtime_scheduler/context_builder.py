from __future__ import annotations

import time
from datetime import datetime, timezone

from apps.api.app.services.runtime_scheduler.contracts import (
    SchedulerTickContext,
)


def build_scheduler_tick_context(
    *,
    scheduler_name: str,
    dry_run: bool,
    trading_enabled: bool,
    execution_mode: str,
) -> SchedulerTickContext:
    return SchedulerTickContext(
        scheduler_name=scheduler_name,
        started_monotonic=time.monotonic(),
        started_at_wall=datetime.now(timezone.utc),
        dry_run=bool(dry_run),
        trading_enabled=bool(trading_enabled),
        execution_mode=str(execution_mode),
    )
