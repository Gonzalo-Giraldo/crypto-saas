from __future__ import annotations

from apps.api.app.services.runtime_scheduler.observability import (
    build_common_journal_payload,
)
from apps.api.app.services.runtime_scheduler.runtime_state import (
    SchedulerRuntimeState,
)
from apps.api.app.services.scheduler_runtime_state_service import (
    record_scheduler_tick_error,
    record_scheduler_tick_ok,
)
from apps.api.app.services.scheduler_tick_journal_service import (
    record_scheduler_tick_journal,
)


def record_scheduler_tick_success_runtime(
    *,
    db,
    scheduler_name: str,
    runtime_state: SchedulerRuntimeState,
    duration_ms: int,
    started_at,
    candidate_symbol,
    candidate_score,
    observation_report,
    observation_payload,
):
    record_scheduler_tick_ok(
        db,
        scheduler_name=scheduler_name,
        duration_ms=duration_ms,
        dry_run=runtime_state.scheduler_dry_run,
        trading_enabled=runtime_state.trading_enabled,
        last_candidate_symbol=candidate_symbol,
        last_candidate_score=candidate_score,
        last_execution_mode=runtime_state.execution_mode,
    )

    common_journal_payload = build_common_journal_payload(
        started_at=started_at,
        finished_at=None,
        duration_ms=duration_ms,
        dry_run=runtime_state.scheduler_dry_run,
        trading_enabled=runtime_state.trading_enabled,
        execution_mode=runtime_state.execution_mode,
    )

    record_scheduler_tick_journal(
        db,
        scheduler_name=scheduler_name,
        status="OK",
        **common_journal_payload,
        candidate_symbol=candidate_symbol,
        candidate_score=candidate_score,
        decision_status=observation_report.decision_status,
        selected_rank=observation_report.selected_rank,
        ranked_count=observation_report.ranked_count,
        top_n=observation_report.top_n,
        observation_payload=observation_payload,
        analytics_exported=False,
    )


def record_scheduler_tick_error_runtime(
    *,
    db,
    scheduler_name: str,
    runtime_state: SchedulerRuntimeState,
    duration_ms: int,
    started_at,
    error: str,
):
    record_scheduler_tick_error(
        db,
        scheduler_name=scheduler_name,
        duration_ms=duration_ms,
        dry_run=runtime_state.scheduler_dry_run,
        trading_enabled=runtime_state.trading_enabled,
        last_error=error,
        last_execution_mode=runtime_state.execution_mode,
    )

    common_journal_payload = build_common_journal_payload(
        started_at=started_at,
        finished_at=None,
        duration_ms=duration_ms,
        dry_run=runtime_state.scheduler_dry_run,
        trading_enabled=runtime_state.trading_enabled,
        execution_mode=runtime_state.execution_mode,
    )

    record_scheduler_tick_journal(
        db,
        scheduler_name=scheduler_name,
        status="ERROR",
        **common_journal_payload,
        error=error,
    )
