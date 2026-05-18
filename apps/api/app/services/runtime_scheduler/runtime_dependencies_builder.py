from __future__ import annotations

from apps.api.app.services.runtime_scheduler.runtime_dependencies import (
    SchedulerRuntimeDependencies,
)


def build_scheduler_runtime_dependencies(
    *,
    legacy_exit_tick,
    legacy_market_monitor_tick,
    legacy_auto_pick_tick,
    legacy_learning_tick,
    global_shadow_tick,
) -> SchedulerRuntimeDependencies:
    return SchedulerRuntimeDependencies(
        legacy_exit_tick=legacy_exit_tick,
        legacy_market_monitor_tick=legacy_market_monitor_tick,
        legacy_auto_pick_tick=legacy_auto_pick_tick,
        legacy_learning_tick=legacy_learning_tick,
        global_shadow_tick=global_shadow_tick,
    )
