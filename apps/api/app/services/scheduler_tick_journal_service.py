from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from apps.api.app.models.scheduler_tick_journal import SchedulerTickJournal


def record_scheduler_tick_journal(
    db: Session,
    *,
    scheduler_name: str,
    started_at: datetime,
    finished_at: datetime,
    status: str,
    dry_run: bool,
    trading_enabled: bool,
    duration_ms: int | None = None,
    overlap_blocked: bool = False,
    runtime_locked: bool = False,
    candidate_symbol: str | None = None,
    candidate_score: str | None = None,
    execution_mode: str | None = None,
    decision_status: str | None = None,
    selected_rank: int | None = None,
    ranked_count: int | None = None,
    top_n: int | None = None,
    observation_payload: dict | None = None,
    analytics_exported: bool = False,
    mutation_attempted: bool = False,
    mutation_executed: bool = False,
    error: str | None = None,
) -> SchedulerTickJournal:
    scheduler_name_value = str(scheduler_name or "").strip()
    if not scheduler_name_value:
        raise ValueError("scheduler_name_required")

    status_value = str(status or "UNKNOWN").upper().strip()
    if not status_value:
        status_value = "UNKNOWN"

    started_at_value = started_at
    finished_at_value = finished_at

    if started_at_value.tzinfo is None:
        started_at_value = started_at_value.replace(tzinfo=timezone.utc)

    if finished_at_value.tzinfo is None:
        finished_at_value = finished_at_value.replace(tzinfo=timezone.utc)

    duration_value = duration_ms
    if duration_value is None:
        duration_value = max(0, int((finished_at_value - started_at_value).total_seconds() * 1000))

    row = SchedulerTickJournal(
        tick_id=str(uuid.uuid4()),
        scheduler_name=scheduler_name_value,
        started_at=started_at_value,
        finished_at=finished_at_value,
        duration_ms=max(0, int(duration_value)),
        status=status_value,
        overlap_blocked=bool(overlap_blocked),
        runtime_locked=bool(runtime_locked),
        dry_run=bool(dry_run),
        trading_enabled=bool(trading_enabled),
        candidate_symbol=candidate_symbol,
        candidate_score=candidate_score,
        execution_mode=execution_mode,
        decision_status=str(decision_status).upper().strip() if decision_status else None,
        selected_rank=int(selected_rank) if selected_rank is not None else None,
        ranked_count=int(ranked_count) if ranked_count is not None else None,
        top_n=int(top_n) if top_n is not None else None,
        observation_payload_json=json.dumps(observation_payload, sort_keys=True) if observation_payload is not None else None,
        analytics_exported=bool(analytics_exported),
        mutation_attempted=bool(mutation_attempted),
        mutation_executed=bool(mutation_executed),
        error=error,
    )
    db.add(row)
    db.flush()
    return row


def load_recent_scheduler_tick_journal(
    db: Session,
    *,
    scheduler_name: str,
    limit: int = 25,
) -> list[SchedulerTickJournal]:
    scheduler_name_value = str(scheduler_name or "").strip()
    if not scheduler_name_value:
        return []

    safe_limit = min(max(int(limit or 25), 1), 100)

    return (
        db.query(SchedulerTickJournal)
        .filter(SchedulerTickJournal.scheduler_name == scheduler_name_value)
        .order_by(SchedulerTickJournal.started_at.desc())
        .limit(safe_limit)
        .all()
    )
