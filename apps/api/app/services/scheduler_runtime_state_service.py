from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import update
from sqlalchemy.orm import Session

from apps.api.app.models.scheduler_runtime_state import SchedulerRuntimeState


AUTO_PICK_SCHEDULER_NAME = "auto_pick_internal"


def upsert_scheduler_runtime_state(
    db: Session,
    *,
    scheduler_name: str,
    last_tick_status: str,
    dry_run: bool,
    trading_enabled: bool,
    last_tick_duration_ms: int | None = None,
    last_error: str | None = None,
    overlap_blocked: bool = False,
    runtime_locked: bool = False,
    last_candidate_symbol: str | None = None,
    last_candidate_score: str | None = None,
    last_execution_mode: str | None = None,
    runtime_owner_id: str | None = None,
    runtime_instance_id: str | None = None,
    runtime_generation: int | None = None,
    runtime_started_at: datetime | None = None,
    runtime_heartbeat_at: datetime | None = None,
) -> SchedulerRuntimeState:
    scheduler_name_value = str(scheduler_name or "").strip()
    if not scheduler_name_value:
        raise ValueError("scheduler_name_required")

    status_value = str(last_tick_status or "UNKNOWN").upper().strip()
    if not status_value:
        status_value = "UNKNOWN"

    row = db.get(SchedulerRuntimeState, scheduler_name_value)

    if row is None:
        row = SchedulerRuntimeState(scheduler_name=scheduler_name_value)
        db.add(row)

    row.last_tick_at = datetime.now(timezone.utc)
    row.last_tick_status = status_value
    row.last_tick_duration_ms = last_tick_duration_ms
    row.last_error = last_error
    row.overlap_blocked = bool(overlap_blocked)
    row.runtime_locked = bool(runtime_locked)
    row.dry_run = bool(dry_run)
    row.trading_enabled = bool(trading_enabled)
    row.last_candidate_symbol = last_candidate_symbol
    row.last_candidate_score = last_candidate_score
    row.last_execution_mode = last_execution_mode

    row.runtime_owner_id = runtime_owner_id
    row.runtime_instance_id = runtime_instance_id
    row.runtime_generation = runtime_generation
    row.runtime_started_at = runtime_started_at
    row.runtime_heartbeat_at = runtime_heartbeat_at

    db.flush()
    return row


def get_scheduler_runtime_state(
    db: Session,
    *,
    scheduler_name: str,
) -> SchedulerRuntimeState | None:
    scheduler_name_value = str(scheduler_name or "").strip()
    if not scheduler_name_value:
        return None

    return db.get(SchedulerRuntimeState, scheduler_name_value)


def record_scheduler_tick_ok(
    db: Session,
    *,
    scheduler_name: str,
    duration_ms: int,
    dry_run: bool,
    trading_enabled: bool,
    last_candidate_symbol: str | None = None,
    last_candidate_score: str | None = None,
    last_execution_mode: str | None = None,
) -> SchedulerRuntimeState:
    return upsert_scheduler_runtime_state(
        db,
        scheduler_name=scheduler_name,
        last_tick_status="OK",
        last_tick_duration_ms=duration_ms,
        dry_run=dry_run,
        trading_enabled=trading_enabled,
        last_error=None,
        overlap_blocked=False,
        runtime_locked=False,
        last_candidate_symbol=last_candidate_symbol,
        last_candidate_score=last_candidate_score,
        last_execution_mode=last_execution_mode,
    )


def record_scheduler_tick_error(
    db: Session,
    *,
    scheduler_name: str,
    duration_ms: int,
    dry_run: bool,
    trading_enabled: bool,
    last_error: str,
    last_execution_mode: str | None = None,
) -> SchedulerRuntimeState:
    return upsert_scheduler_runtime_state(
        db,
        scheduler_name=scheduler_name,
        last_tick_status="ERROR",
        last_tick_duration_ms=duration_ms,
        dry_run=dry_run,
        trading_enabled=trading_enabled,
        last_error=last_error,
        overlap_blocked=False,
        runtime_locked=False,
        last_execution_mode=last_execution_mode,
    )


def record_scheduler_overlap_blocked(
    db: Session,
    *,
    scheduler_name: str,
    dry_run: bool,
    trading_enabled: bool,
    last_execution_mode: str | None = None,
) -> SchedulerRuntimeState:
    return upsert_scheduler_runtime_state(
        db,
        scheduler_name=scheduler_name,
        last_tick_status="OVERLAP_BLOCKED",
        dry_run=dry_run,
        trading_enabled=trading_enabled,
        last_error=None,
        overlap_blocked=True,
        runtime_locked=True,
        last_execution_mode=last_execution_mode,
    )


def update_scheduler_runtime_ownership(
    db: Session,
    *,
    scheduler_name: str,
    runtime_owner_id: str | None,
    runtime_instance_id: str | None,
    runtime_generation: int | None,
    runtime_started_at: datetime | None,
    runtime_heartbeat_at: datetime | None,
) -> SchedulerRuntimeState:
    row = get_scheduler_runtime_state(
        db,
        scheduler_name=scheduler_name,
    )

    if row is None:
        raise ValueError("scheduler_runtime_state_not_found")

    row.runtime_owner_id = runtime_owner_id
    row.runtime_instance_id = runtime_instance_id
    row.runtime_generation = runtime_generation
    row.runtime_started_at = runtime_started_at
    row.runtime_heartbeat_at = runtime_heartbeat_at

    db.flush()

    return row


def clear_scheduler_runtime_ownership(
    db: Session,
    *,
    scheduler_name: str,
) -> SchedulerRuntimeState:
    row = get_scheduler_runtime_state(
        db,
        scheduler_name=scheduler_name,
    )

    if row is None:
        raise ValueError("scheduler_runtime_state_not_found")

    row.runtime_owner_id = None
    row.runtime_instance_id = None
    row.runtime_generation = None
    row.runtime_started_at = None
    row.runtime_heartbeat_at = None

    db.flush()

    return row


def touch_scheduler_runtime_heartbeat(
    db: Session,
    *,
    scheduler_name: str,
    runtime_heartbeat_at: datetime,
) -> SchedulerRuntimeState:
    row = get_scheduler_runtime_state(
        db,
        scheduler_name=scheduler_name,
    )

    if row is None:
        raise ValueError("scheduler_runtime_state_not_found")

    row.runtime_heartbeat_at = runtime_heartbeat_at

    db.flush()

    return row


def touch_scheduler_runtime_heartbeat_owned(
    db: Session,
    *,
    scheduler_name: str,
    runtime_owner_id: str,
    runtime_instance_id: str,
    runtime_generation: int,
    runtime_heartbeat_at: datetime,
) -> SchedulerRuntimeState:
    scheduler_name_value = str(scheduler_name or "").strip()
    runtime_owner_id_value = str(runtime_owner_id or "").strip()
    runtime_instance_id_value = str(runtime_instance_id or "").strip()

    if not scheduler_name_value:
        raise ValueError("scheduler_name_required")

    if not runtime_owner_id_value:
        raise ValueError("runtime_owner_id_required")

    if not runtime_instance_id_value:
        raise ValueError("runtime_instance_id_required")

    if runtime_generation <= 0:
        raise ValueError("runtime_generation_must_be_positive")

    if runtime_heartbeat_at.tzinfo is None:
        raise ValueError("runtime_heartbeat_at_must_be_timezone_aware")

    stmt = (
        update(SchedulerRuntimeState)
        .where(SchedulerRuntimeState.scheduler_name == scheduler_name_value)
        .where(SchedulerRuntimeState.runtime_owner_id == runtime_owner_id_value)
        .where(SchedulerRuntimeState.runtime_instance_id == runtime_instance_id_value)
        .where(SchedulerRuntimeState.runtime_generation == runtime_generation)
        .values(runtime_heartbeat_at=runtime_heartbeat_at)
    )

    result = db.execute(stmt)

    if result.rowcount != 1:
        raise ValueError("runtime_heartbeat_owner_mismatch")

    row = get_scheduler_runtime_state(
        db,
        scheduler_name=scheduler_name_value,
    )

    if row is None:
        raise ValueError("scheduler_runtime_state_not_found")

    db.flush()

    return row


def clear_scheduler_runtime_ownership_owned(
    db: Session,
    *,
    scheduler_name: str,
    runtime_owner_id: str,
    runtime_instance_id: str,
    runtime_generation: int,
) -> SchedulerRuntimeState:
    scheduler_name_value = str(scheduler_name or "").strip()
    runtime_owner_id_value = str(runtime_owner_id or "").strip()
    runtime_instance_id_value = str(runtime_instance_id or "").strip()

    if not scheduler_name_value:
        raise ValueError("scheduler_name_required")

    if not runtime_owner_id_value:
        raise ValueError("runtime_owner_id_required")

    if not runtime_instance_id_value:
        raise ValueError("runtime_instance_id_required")

    if runtime_generation <= 0:
        raise ValueError("runtime_generation_must_be_positive")

    stmt = (
        update(SchedulerRuntimeState)
        .where(SchedulerRuntimeState.scheduler_name == scheduler_name_value)
        .where(SchedulerRuntimeState.runtime_owner_id == runtime_owner_id_value)
        .where(SchedulerRuntimeState.runtime_instance_id == runtime_instance_id_value)
        .where(SchedulerRuntimeState.runtime_generation == runtime_generation)
        .values(
            runtime_owner_id=None,
            runtime_instance_id=None,
            runtime_generation=None,
            runtime_started_at=None,
            runtime_heartbeat_at=None,
        )
    )

    result = db.execute(stmt)

    if result.rowcount != 1:
        raise ValueError("runtime_ownership_owner_mismatch")

    row = get_scheduler_runtime_state(
        db,
        scheduler_name=scheduler_name_value,
    )

    if row is None:
        raise ValueError("scheduler_runtime_state_not_found")

    db.flush()

    return row
