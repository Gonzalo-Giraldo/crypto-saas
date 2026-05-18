from __future__ import annotations

import threading
import time
from collections.abc import Callable
from datetime import datetime, timezone

from sqlalchemy import text

from apps.api.app.core.config import settings
from apps.api.app.db.session import SessionLocal, engine
from apps.api.app.services.scheduler_runtime_state_service import (
    AUTO_PICK_SCHEDULER_NAME,
    record_scheduler_overlap_blocked,
)
from apps.api.app.services.scheduler_tick_journal_service import record_scheduler_tick_journal
from apps.api.app.services.scheduler_lifecycle_state import (
    SchedulerLifecycleState,
)
from apps.api.app.services.trading_controls import get_trading_enabled


_AUTO_PICK_TICK_LOCK_KEY = 887731
_scheduler_stop_event = threading.Event()
_scheduler_thread: threading.Thread | None = None
_scheduler_tick_once: Callable[[], None] | None = None
_scheduler_lifecycle_state = SchedulerLifecycleState.STOPPED


def _record_overlap_blocked() -> None:
    db = SessionLocal()
    started_at_wall = datetime.now(timezone.utc)
    try:
        trading_enabled = bool(get_trading_enabled(db))
        execution_mode = "dry_run" if bool(settings.AUTO_PICK_INTERNAL_SCHEDULER_DRY_RUN) else "live"
        record_scheduler_overlap_blocked(
            db,
            scheduler_name=AUTO_PICK_SCHEDULER_NAME,
            dry_run=bool(settings.AUTO_PICK_INTERNAL_SCHEDULER_DRY_RUN),
            trading_enabled=trading_enabled,
            last_execution_mode=execution_mode,
        )
        record_scheduler_tick_journal(
            db,
            scheduler_name=AUTO_PICK_SCHEDULER_NAME,
            started_at=started_at_wall,
            finished_at=datetime.now(timezone.utc),
            duration_ms=0,
            status="OVERLAP_BLOCKED",
            dry_run=bool(settings.AUTO_PICK_INTERNAL_SCHEDULER_DRY_RUN),
            trading_enabled=trading_enabled,
            overlap_blocked=True,
            runtime_locked=True,
            execution_mode=execution_mode,
            mutation_attempted=False,
            mutation_executed=False,
        )
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


def _run_tick_once_with_lock() -> None:
    if _scheduler_tick_once is None:
        raise RuntimeError("scheduler_tick_once_not_configured")

    if settings.DATABASE_URL.startswith("sqlite"):
        _scheduler_tick_once()
        return

    with engine.begin() as conn:
        got_lock = bool(
            conn.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": _AUTO_PICK_TICK_LOCK_KEY}).scalar()
        )

    if not got_lock:
        _record_overlap_blocked()
        return

    try:
        _scheduler_tick_once()
    finally:
        with engine.begin() as conn:
            conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": _AUTO_PICK_TICK_LOCK_KEY})


def _scheduler_loop() -> None:
    interval_minutes = max(1, int(settings.AUTO_PICK_INTERNAL_SCHEDULER_INTERVAL_MINUTES))
    interval_seconds = interval_minutes * 60
    while not _scheduler_stop_event.is_set():
        now = time.time()
        wait_seconds = interval_seconds - (now % interval_seconds)
        if _scheduler_stop_event.wait(timeout=wait_seconds):
            break
        _run_tick_once_with_lock()


def start_auto_pick_scheduler(tick_once: Callable[[], None]) -> None:
    global _scheduler_thread, _scheduler_tick_once, _scheduler_lifecycle_state
    if not settings.AUTO_PICK_INTERNAL_SCHEDULER_ENABLED:
        return
    if _scheduler_thread and _scheduler_thread.is_alive():
        return
    if _scheduler_tick_once is not None and _scheduler_tick_once is not tick_once:
        raise RuntimeError("scheduler_tick_once_already_bound")
    _scheduler_tick_once = tick_once
    _scheduler_lifecycle_state = SchedulerLifecycleState.RUNNING
    _scheduler_stop_event.clear()
    _scheduler_thread = threading.Thread(target=_scheduler_loop, name="auto-pick-scheduler", daemon=True)
    _scheduler_thread.start()
    print("[auto-pick-scheduler] started", flush=True)


def stop_auto_pick_scheduler() -> None:
    global _scheduler_lifecycle_state
    _scheduler_lifecycle_state = SchedulerLifecycleState.STOPPING
    _scheduler_stop_event.set()


def get_scheduler_lifecycle_state() -> SchedulerLifecycleState:
    return _scheduler_lifecycle_state


def get_effective_scheduler_lifecycle_state() -> SchedulerLifecycleState:
    thread_alive = bool(_scheduler_thread and _scheduler_thread.is_alive())

    if _scheduler_lifecycle_state == SchedulerLifecycleState.STOPPING and not thread_alive:
        return SchedulerLifecycleState.STOPPED

    if _scheduler_lifecycle_state == SchedulerLifecycleState.RUNNING and not thread_alive:
        return SchedulerLifecycleState.STOPPED

    return _scheduler_lifecycle_state


def is_scheduler_thread_alive() -> bool:
    return bool(_scheduler_thread and _scheduler_thread.is_alive())
