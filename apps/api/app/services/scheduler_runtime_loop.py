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
    clear_scheduler_runtime_ownership_owned,
    get_scheduler_runtime_state,
    record_scheduler_overlap_blocked,
    touch_scheduler_runtime_heartbeat_owned,
    upsert_scheduler_runtime_state,
)
from apps.api.app.services.runtime_scheduler.runtime_advisory_session_service import (
    acquire_runtime_advisory_session,
    release_runtime_advisory_session,
    refresh_runtime_advisory_session_state,
)
from apps.api.app.services.runtime_scheduler.runtime_ownership_service import (
    acquire_runtime_ownership,
)
from apps.api.app.services.runtime_scheduler.runtime_session_identity import (
    clear_runtime_session_generation,
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
_runtime_ownership = None
_runtime_advisory_session_lock = None



def _acquire_runtime_authority() -> bool:
    global _runtime_ownership, _runtime_advisory_session_lock

    db = SessionLocal()
    try:
        runtime_state = get_scheduler_runtime_state(
            db,
            scheduler_name=AUTO_PICK_SCHEDULER_NAME,
        )
        if runtime_state is None:
            runtime_state = upsert_scheduler_runtime_state(
                db,
                scheduler_name=AUTO_PICK_SCHEDULER_NAME,
                last_tick_status="INIT",
                dry_run=bool(settings.AUTO_PICK_INTERNAL_SCHEDULER_DRY_RUN),
                trading_enabled=bool(get_trading_enabled(db)),
            )
            db.commit()

        ownership = acquire_runtime_ownership(
            db,
            runtime_state=runtime_state,
            now=datetime.now(timezone.utc),
        )

        if not ownership.acquired:
            db.rollback()
            print(
                "[auto-pick-scheduler] runtime ownership not acquired",
                ownership.reason,
                flush=True,
            )
            return False

        db.commit()

        advisory = acquire_runtime_advisory_session(
            engine=engine,
            scheduler_name=AUTO_PICK_SCHEDULER_NAME,
        )

        if not advisory.state.valid:
            try:
                clear_scheduler_runtime_ownership_owned(
                    db,
                    scheduler_name=AUTO_PICK_SCHEDULER_NAME,
                    runtime_owner_id=ownership.runtime_owner_id,
                    runtime_instance_id=ownership.runtime_instance_id,
                    runtime_generation=ownership.runtime_generation,
                )
                db.commit()
            except Exception:
                db.rollback()
            clear_runtime_session_generation(
                scheduler_name=AUTO_PICK_SCHEDULER_NAME,
            )
            print(
                "[auto-pick-scheduler] runtime advisory session not acquired",
                advisory.state.reason,
                flush=True,
            )
            return False

        _runtime_ownership = ownership
        _runtime_advisory_session_lock = advisory.lock
        return True
    except Exception as exc:
        db.rollback()
        print(
            f"[auto-pick-scheduler] runtime authority acquire failed: {exc}",
            flush=True,
        )
        return False
    finally:
        db.close()


def _release_runtime_authority() -> None:
    global _runtime_ownership, _runtime_advisory_session_lock

    ownership = _runtime_ownership
    lock = _runtime_advisory_session_lock

    try:
        release_runtime_advisory_session(
            scheduler_name=AUTO_PICK_SCHEDULER_NAME,
            lock=lock,
        )
    except Exception as exc:
        print(
            f"[auto-pick-scheduler] runtime advisory release failed: {exc}",
            flush=True,
        )

    if ownership is not None and ownership.acquired:
        db = SessionLocal()
        try:
            clear_scheduler_runtime_ownership_owned(
                db,
                scheduler_name=AUTO_PICK_SCHEDULER_NAME,
                runtime_owner_id=ownership.runtime_owner_id,
                runtime_instance_id=ownership.runtime_instance_id,
                runtime_generation=ownership.runtime_generation,
            )
            db.commit()
        except Exception as exc:
            db.rollback()
            print(
                f"[auto-pick-scheduler] runtime ownership release failed: {exc}",
                flush=True,
            )
        finally:
            db.close()

    clear_runtime_session_generation(
        scheduler_name=AUTO_PICK_SCHEDULER_NAME,
    )
    _runtime_advisory_session_lock = None
    _runtime_ownership = None


def _touch_runtime_authority_heartbeat() -> bool:
    ownership = _runtime_ownership
    if ownership is None or not ownership.acquired:
        return False

    advisory_state = refresh_runtime_advisory_session_state(
        scheduler_name=AUTO_PICK_SCHEDULER_NAME,
        lock=_runtime_advisory_session_lock,
    )
    if not advisory_state.valid:
        print(
            "[auto-pick-scheduler] runtime advisory session lost",
            advisory_state.reason,
            flush=True,
        )
        return False

    db = SessionLocal()
    try:
        touch_scheduler_runtime_heartbeat_owned(
            db,
            scheduler_name=AUTO_PICK_SCHEDULER_NAME,
            runtime_owner_id=ownership.runtime_owner_id,
            runtime_instance_id=ownership.runtime_instance_id,
            runtime_generation=ownership.runtime_generation,
            runtime_heartbeat_at=datetime.now(timezone.utc),
        )
        db.commit()
        return True
    except Exception as exc:
        db.rollback()
        print(
            f"[auto-pick-scheduler] runtime heartbeat failed: {exc}",
            flush=True,
        )
        return False
    finally:
        db.close()


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
        if not _touch_runtime_authority_heartbeat():
            _scheduler_stop_event.set()
            break

        now = time.time()
        wait_seconds = interval_seconds - (now % interval_seconds)
        if _scheduler_stop_event.wait(timeout=wait_seconds):
            break

        if not _touch_runtime_authority_heartbeat():
            _scheduler_stop_event.set()
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
    if not _acquire_runtime_authority():
        _scheduler_lifecycle_state = SchedulerLifecycleState.STOPPED
        return
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
    _release_runtime_authority()


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
