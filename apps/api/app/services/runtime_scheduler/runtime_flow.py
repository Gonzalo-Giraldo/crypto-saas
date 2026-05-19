from __future__ import annotations

from apps.api.app.core.config import settings
from apps.api.app.services.auto_pick.binance.orchestrator import (
    run_binance_auto_pick_observation,
)
from apps.api.app.services.runtime_scheduler.context_builder import (
    elapsed_ms_since,
    extract_candidate_metadata,
)
from apps.api.app.services.runtime_scheduler.observability import (
    build_tick_details,
)
from apps.api.app.services.runtime_scheduler.runtime_flow_result_builder import (
    build_scheduler_runtime_flow_result,
)
from apps.api.app.services.runtime_scheduler.runtime_dependencies import (
    SchedulerRuntimeDependencies,
)


def _attach_shadow_payload(
    *,
    observation_payload: dict,
    shadow_out,
) -> dict:
    if shadow_out is None:
        return observation_payload

    observation_payload["shadow"] = shadow_out
    return observation_payload


def execute_scheduler_runtime_flow(
    *,
    db,
    started_at,
    scheduler_dry_run: bool,
    dependencies: SchedulerRuntimeDependencies,
):
    exit_out = {
        "scanned_positions": 0,
        "exit_candidates": 0,
        "closed_positions": 0,
        "skipped_no_price": 0,
        "skipped_by_policy": 0,
        "errors": 0,
        "paused": False,
        "dry_run": True,
    }

    if bool(settings.AUTO_EXIT_INTERNAL_ENABLED):
        exit_out = dependencies.legacy_exit_tick(
            db=db,
            tenant_id=settings.AUTO_PICK_INTERNAL_TENANT_ID or "default",
            dry_run=bool(settings.AUTO_EXIT_INTERNAL_DRY_RUN),
            real_only=bool(settings.AUTO_EXIT_INTERNAL_REAL_ONLY),
            include_service_users=bool(
                settings.AUTO_EXIT_INTERNAL_INCLUDE_SERVICE_USERS
            ),
            max_positions=int(
                settings.AUTO_EXIT_INTERNAL_MAX_POSITIONS or 500
            ),
        )

    monitor = {"inserted": 0, "legacy_enabled": False}

    if bool(settings.AUTO_PICK_LEGACY_MARKET_MONITOR_ENABLED):
        monitor = dependencies.legacy_market_monitor_tick(
            db=db,
            tenant_id=settings.AUTO_PICK_INTERNAL_TENANT_ID or "default",
        )
        monitor["legacy_enabled"] = True

    out = {
        "executed_count": 0,
        "dry_run": scheduler_dry_run,
        "top_n": int(settings.AUTO_PICK_INTERNAL_SCHEDULER_TOP_N),
        "legacy_enabled": False,
    }

    if bool(settings.AUTO_PICK_LEGACY_TICK_ENABLED):
        out = dependencies.legacy_auto_pick_tick(
            db=db,
            tenant_id=settings.AUTO_PICK_INTERNAL_TENANT_ID or "default",
            dry_run=scheduler_dry_run,
            top_n=int(settings.AUTO_PICK_INTERNAL_SCHEDULER_TOP_N),
            real_only=bool(settings.AUTO_PICK_INTERNAL_REAL_ONLY),
            include_service_users=bool(
                settings.AUTO_PICK_INTERNAL_INCLUDE_SERVICE_USERS
            ),
        )
        out["legacy_enabled"] = True

    dependencies.legacy_learning_tick(
        db=db,
        tenant_id=settings.AUTO_PICK_INTERNAL_TENANT_ID or "default",
    )

    observation_report = run_binance_auto_pick_observation(
        top_n=int(settings.AUTO_PICK_INTERNAL_SCHEDULER_TOP_N),
    )

    observation_payload = observation_report.to_dict()

    shadow_out = dependencies.global_shadow_tick(db=db)

    observation_payload = _attach_shadow_payload(
        observation_payload=observation_payload,
        shadow_out=shadow_out,
    )

    tick_details = build_tick_details(
        monitor=monitor,
        out=out,
        exit_out=exit_out,
        shadow_out=shadow_out,
    )

    duration_ms = elapsed_ms_since(started_at)

    candidate_symbol, candidate_score = extract_candidate_metadata(
        observation_report
    )

    return (
        build_scheduler_runtime_flow_result(
            duration_ms=duration_ms,
            tick_details=tick_details,
            observation_payload=observation_payload,
            candidate_symbol=candidate_symbol,
            candidate_score=candidate_score,
        ),
        observation_report,
    )
