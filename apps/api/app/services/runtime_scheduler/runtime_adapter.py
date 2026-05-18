from __future__ import annotations

from apps.api.app.services.runtime_scheduler.observability_runtime import (
    record_scheduler_tick_success_runtime,
)
from apps.api.app.services.runtime_scheduler.runtime_dependencies_builder import (
    build_scheduler_runtime_dependencies,
)
from apps.api.app.services.runtime_scheduler.runtime_flow import (
    execute_scheduler_runtime_flow,
)
from apps.api.app.services.runtime_scheduler.runtime_state_builder import (
    build_scheduler_runtime_state,
)


def execute_scheduler_runtime_adapter(
    *,
    db,
    scheduler_name: str,
    started_at,
    started_at_wall,
    scheduler_dry_run: bool,
    trading_enabled,
    legacy_exit_tick,
    legacy_market_monitor_tick,
    legacy_auto_pick_tick,
    legacy_learning_tick,
    global_shadow_tick,
):
    runtime_dependencies = build_scheduler_runtime_dependencies(
        legacy_exit_tick=legacy_exit_tick,
        legacy_market_monitor_tick=legacy_market_monitor_tick,
        legacy_auto_pick_tick=legacy_auto_pick_tick,
        legacy_learning_tick=legacy_learning_tick,
        global_shadow_tick=global_shadow_tick,
    )

    flow_result, observation_report = execute_scheduler_runtime_flow(
        db=db,
        started_at=started_at,
        scheduler_dry_run=scheduler_dry_run,
        dependencies=runtime_dependencies,
    )

    runtime_state = build_scheduler_runtime_state(
        scheduler_dry_run=scheduler_dry_run,
        trading_enabled=trading_enabled,
    )

    record_scheduler_tick_success_runtime(
        db=db,
        scheduler_name=scheduler_name,
        runtime_state=runtime_state,
        duration_ms=flow_result.duration_ms,
        started_at=started_at_wall,
        candidate_symbol=flow_result.candidate_symbol,
        candidate_score=flow_result.candidate_score,
        observation_report=observation_report,
        observation_payload=flow_result.observation_payload,
    )

    return flow_result
