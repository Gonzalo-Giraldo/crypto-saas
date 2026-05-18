from __future__ import annotations

import time
from datetime import datetime, timezone

from apps.api.app.services.runtime_scheduler.contracts import (
    SchedulerTickContext,
)


def elapsed_ms_since(started_monotonic: float) -> int:
    return int((time.monotonic() - started_monotonic) * 1000)


def extract_candidate_metadata(observation_report) -> tuple[str | None, str | None]:
    candidate_symbol = observation_report.selected_symbol
    candidate_score = (
        str(observation_report.selected.final_score)
        if observation_report.selected and observation_report.selected.final_score is not None
        else None
    )
    return candidate_symbol, candidate_score


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
