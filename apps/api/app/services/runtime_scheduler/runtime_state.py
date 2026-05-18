from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SchedulerRuntimeState:
    scheduler_dry_run: bool
    trading_enabled: bool
    execution_mode: str
