from __future__ import annotations

from apps.api.app.services.scheduler_runtime_state_service import (
    record_scheduler_tick_error,
    record_scheduler_tick_ok,
)
from apps.api.app.services.scheduler_tick_journal_service import (
    record_scheduler_tick_journal,
)


def record_tick_success(**kwargs):
    db = kwargs["db"]

    record_scheduler_tick_ok(
        db,
        scheduler_name=kwargs["scheduler_name"],
        duration_ms=kwargs["duration_ms"],
        dry_run=kwargs["dry_run"],
        trading_enabled=kwargs["trading_enabled"],
        last_candidate_symbol=kwargs.get("last_candidate_symbol"),
        last_candidate_score=kwargs.get("last_candidate_score"),
        last_execution_mode=kwargs.get("last_execution_mode"),
    )

    record_scheduler_tick_journal(
        db,
        scheduler_name=kwargs["scheduler_name"],
        started_at=kwargs["started_at"],
        finished_at=kwargs["finished_at"],
        duration_ms=kwargs["duration_ms"],
        status="OK",
        dry_run=kwargs["dry_run"],
        trading_enabled=kwargs["trading_enabled"],
        candidate_symbol=kwargs.get("candidate_symbol"),
        candidate_score=kwargs.get("candidate_score"),
        execution_mode=kwargs.get("execution_mode"),
        decision_status=kwargs.get("decision_status"),
        selected_rank=kwargs.get("selected_rank"),
        ranked_count=kwargs.get("ranked_count"),
        top_n=kwargs.get("top_n"),
        observation_payload=kwargs.get("observation_payload"),
        analytics_exported=False,
        mutation_attempted=False,
        mutation_executed=False,
    )


def record_tick_failure(**kwargs):
    db = kwargs["db"]

    record_scheduler_tick_error(
        db,
        scheduler_name=kwargs["scheduler_name"],
        duration_ms=kwargs["duration_ms"],
        dry_run=kwargs["dry_run"],
        trading_enabled=kwargs["trading_enabled"],
        last_error=kwargs["last_error"],
        last_execution_mode=kwargs["last_execution_mode"],
    )

    record_scheduler_tick_journal(
        db,
        scheduler_name=kwargs["scheduler_name"],
        started_at=kwargs["started_at"],
        finished_at=kwargs["finished_at"],
        duration_ms=kwargs["duration_ms"],
        status="ERROR",
        dry_run=kwargs["dry_run"],
        trading_enabled=kwargs["trading_enabled"],
        execution_mode=kwargs["execution_mode"],
        mutation_attempted=False,
        mutation_executed=False,
        error=kwargs["last_error"],
    )
