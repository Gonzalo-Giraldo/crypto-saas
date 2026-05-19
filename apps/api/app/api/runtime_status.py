from __future__ import annotations

import os
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from apps.api.app.api.deps import require_role
from apps.api.app.core.config import settings
from apps.api.app.db.session import get_db
from apps.api.app.models.binance_exit_protection import BinanceExitProtection
from apps.api.app.models.user import User
from apps.api.app.services.trading_controls import get_trading_enabled
from apps.api.app.services.scheduler_tick_journal_service import load_recent_scheduler_tick_journal
from apps.api.app.services.scheduler_runtime_state_service import (
    AUTO_PICK_SCHEDULER_NAME,
    get_scheduler_runtime_state,
)
from apps.api.app.services.scheduler_runtime_loop import (
    get_effective_scheduler_lifecycle_state,
    get_scheduler_lifecycle_state,
    is_scheduler_thread_alive,
)
from apps.api.app.services.runtime_scheduler.runtime_authority_runtime_snapshot_service import (
    build_runtime_authority_runtime_snapshot,
)


router = APIRouter(prefix="/api/runtime", tags=["runtime"])


def _derive_scheduler_staleness(*, last_tick_at, interval_minutes: int) -> dict:
    if last_tick_at is None:
        return {
            "scheduler_stale": True,
            "stale_duration_seconds": None,
            "operator_attention_required": True,
            "stale_reason": "no_tick_recorded",
        }

    now = datetime.now(timezone.utc)
    tick_at = last_tick_at

    if tick_at.tzinfo is None:
        tick_at = tick_at.replace(tzinfo=timezone.utc)

    stale_duration_seconds = max(0, int((now - tick_at).total_seconds()))
    threshold_seconds = max(1, int(interval_minutes)) * 60 * 2
    scheduler_stale = stale_duration_seconds > threshold_seconds

    return {
        "scheduler_stale": scheduler_stale,
        "stale_duration_seconds": stale_duration_seconds,
        "operator_attention_required": scheduler_stale,
        "stale_reason": "tick_stale" if scheduler_stale else None,
    }


@router.get("/status")
def get_runtime_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    active_protected_positions = (
        db.query(func.count(BinanceExitProtection.id))
        .filter(BinanceExitProtection.market == "FUTURES")
        .filter(BinanceExitProtection.protection_status == "PROTECTED")
        .filter(BinanceExitProtection.sl_status == "SUBMITTED")
        .scalar()
        or 0
    )

    unknown_positions = (
        db.query(func.count(BinanceExitProtection.id))
        .filter(BinanceExitProtection.market == "FUTURES")
        .filter(
            (
                BinanceExitProtection.protection_status == "UNKNOWN"
            )
            | (
                BinanceExitProtection.sl_status == "UNKNOWN"
            )
            | (
                BinanceExitProtection.tp_status == "UNKNOWN"
            )
        )
        .scalar()
        or 0
    )

    pending_cleanup_positions = (
        db.query(func.count(BinanceExitProtection.id))
        .filter(BinanceExitProtection.market == "FUTURES")
        .filter(BinanceExitProtection.last_error.like("replacement_pending_cleanup:%"))
        .scalar()
        or 0
    )

    scheduler_state = get_scheduler_runtime_state(
        db,
        scheduler_name=AUTO_PICK_SCHEDULER_NAME,
    )
    scheduler_interval_minutes = int(settings.AUTO_PICK_INTERNAL_SCHEDULER_INTERVAL_MINUTES)
    scheduler_staleness = _derive_scheduler_staleness(
        last_tick_at=scheduler_state.last_tick_at if scheduler_state else None,
        interval_minutes=scheduler_interval_minutes,
    )
    runtime_authority_snapshot = build_runtime_authority_runtime_snapshot(
        scheduler_name=AUTO_PICK_SCHEDULER_NAME,
        scheduler_state=scheduler_state,
        scheduler_interval_minutes=scheduler_interval_minutes,
        runtime_health_valid=bool(is_scheduler_thread_alive()),
    )
    ownership_lifecycle = runtime_authority_snapshot.ownership_lifecycle
    recent_ticks = load_recent_scheduler_tick_journal(
        db,
        scheduler_name=AUTO_PICK_SCHEDULER_NAME,
        limit=10,
    )

    return {
        "runtime": {
            "service": "api",
            "commit": str(os.getenv("RENDER_GIT_COMMIT") or "unknown"),
            "branch": str(os.getenv("RENDER_GIT_BRANCH") or "unknown"),
            "environment": str(os.getenv("ENVIRONMENT") or os.getenv("APP_ENV") or "unknown"),
            "trading_enabled": bool(get_trading_enabled(db)),
            "scheduler_enabled": bool(settings.AUTO_PICK_INTERNAL_SCHEDULER_ENABLED),
            "scheduler_interval_minutes": scheduler_interval_minutes,
            "scheduler_dry_run": bool(settings.AUTO_PICK_INTERNAL_SCHEDULER_DRY_RUN),
        },
        "scheduler_lifecycle": {
            "desired_state": get_scheduler_lifecycle_state().value,
            "effective_state": get_effective_scheduler_lifecycle_state().value,
            "thread_alive": bool(is_scheduler_thread_alive()),
        },
        "protections": {
            "active_protected_positions": int(active_protected_positions),
            "unknown_positions": int(unknown_positions),
            "pending_cleanup_positions": int(pending_cleanup_positions),
        },
        "autopick": {
            "last_tick_at": scheduler_state.last_tick_at.isoformat() if scheduler_state and scheduler_state.last_tick_at else None,
            "last_tick_status": scheduler_state.last_tick_status if scheduler_state else "UNKNOWN",
            "last_tick_duration_ms": scheduler_state.last_tick_duration_ms if scheduler_state else None,
            "last_error": scheduler_state.last_error if scheduler_state else None,
            "overlap_blocked": bool(scheduler_state.overlap_blocked) if scheduler_state else False,
            "runtime_locked": bool(scheduler_state.runtime_locked) if scheduler_state else False,
            "dry_run": bool(scheduler_state.dry_run) if scheduler_state else bool(settings.AUTO_PICK_INTERNAL_SCHEDULER_DRY_RUN),
            "trading_enabled": bool(scheduler_state.trading_enabled) if scheduler_state else bool(get_trading_enabled(db)),
            "last_candidate_symbol": scheduler_state.last_candidate_symbol if scheduler_state else None,
            "last_candidate_score": scheduler_state.last_candidate_score if scheduler_state else None,
            "last_execution_mode": scheduler_state.last_execution_mode if scheduler_state else None,
            "source": "scheduler_runtime_state" if scheduler_state else "not_yet_instrumented",
            "ownership_lifecycle_state": ownership_lifecycle.state.value if ownership_lifecycle else None,
            "ownership_valid": ownership_lifecycle.valid_ownership if ownership_lifecycle else False,
            "ownership_stale": ownership_lifecycle.stale if ownership_lifecycle else True,
            "ownership_operator_attention_required": ownership_lifecycle.operator_attention_required if ownership_lifecycle else True,
            "ownership_reason": ownership_lifecycle.reason if ownership_lifecycle else "scheduler_runtime_state_missing",

            "local_runtime_owner_id": runtime_authority_snapshot.local_runtime_identity.runtime_owner_id,
            "local_runtime_instance_id": runtime_authority_snapshot.local_runtime_identity.runtime_instance_id,
            "local_identity_matches": runtime_authority_snapshot.local_identity_matches,
            "local_runtime_generation": runtime_authority_snapshot.local_runtime_state.runtime_generation,
            "durable_runtime_generation": scheduler_state.runtime_generation if scheduler_state else None,
            "generation_matches": runtime_authority_snapshot.generation_matches,
            "generation_reconciliation_reason": runtime_authority_snapshot.generation_reconciliation.reason,
            "advisory_session_valid": runtime_authority_snapshot.advisory_session_valid,
            "advisory_session_reason": runtime_authority_snapshot.advisory_session_reason,

            "session_authority_valid": runtime_authority_snapshot.runtime_authority.valid,
            "session_authority_reason": runtime_authority_snapshot.runtime_authority.reason,
            "runtime_authority_state": runtime_authority_snapshot.runtime_authority_state.state.value,
            "runtime_authority_operator_attention_required": runtime_authority_snapshot.runtime_authority_state.operator_attention_required,

            **scheduler_staleness,
        },
        "scheduler_tick_journal": [
            {
                "tick_id": row.tick_id,
                "scheduler_name": row.scheduler_name,
                "started_at": row.started_at.isoformat() if row.started_at else None,
                "finished_at": row.finished_at.isoformat() if row.finished_at else None,
                "duration_ms": row.duration_ms,
                "status": row.status,
                "overlap_blocked": bool(row.overlap_blocked),
                "runtime_locked": bool(row.runtime_locked),
                "dry_run": bool(row.dry_run),
                "trading_enabled": bool(row.trading_enabled),
                "candidate_symbol": row.candidate_symbol,
                "candidate_score": row.candidate_score,
                "execution_mode": row.execution_mode,

                "decision_status": row.decision_status,
                "selected_rank": row.selected_rank,
                "ranked_count": row.ranked_count,
                "top_n": row.top_n,
                "analytics_exported": bool(row.analytics_exported),

                "observation_payload": (
                    json.loads(row.observation_payload_json)
                    if row.observation_payload_json
                    else None
                ),

                "mutation_attempted": bool(row.mutation_attempted),
                "mutation_executed": bool(row.mutation_executed),
                "error": row.error,
            }
            for row in recent_ticks
        ],
        "mutations": [],
    }
