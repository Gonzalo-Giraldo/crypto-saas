from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class SchedulerTickContext:
    scheduler_name: str

    started_monotonic: float
    started_at_wall: datetime

    dry_run: bool
    trading_enabled: bool
    execution_mode: str

    tick_id: str | None = None
    runtime_instance_id: str | None = None
