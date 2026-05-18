from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class SchedulerTickContext:
    scheduler_name: str

    started_monotonic: float
    started_at_wall: datetime

    dry_run: bool | None = None
    trading_enabled: bool | None = None
    execution_mode: str | None = None

    tick_id: str | None = None
    runtime_instance_id: str | None = None
