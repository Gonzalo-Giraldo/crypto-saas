from __future__ import annotations

from apps.api.app.services.runtime_scheduler.context_builder import (
    resolve_execution_mode,
    resolve_trading_enabled,
)
from apps.api.app.services.runtime_scheduler.runtime_state import (
    SchedulerRuntimeState,
)


def build_scheduler_runtime_state(
    *,
    scheduler_dry_run: bool,
    trading_enabled,
) -> SchedulerRuntimeState:
    resolved_trading_enabled = resolve_trading_enabled(trading_enabled)

    return SchedulerRuntimeState(
        scheduler_dry_run=bool(scheduler_dry_run),
        trading_enabled=resolved_trading_enabled,
        execution_mode=resolve_execution_mode(
            dry_run=bool(scheduler_dry_run)
        ),
    )
