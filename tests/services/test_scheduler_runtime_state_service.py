from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.app.db.session import Base
from apps.api.app.models.scheduler_runtime_state import SchedulerRuntimeState
from apps.api.app.services.scheduler_runtime_state_service import (
    AUTO_PICK_SCHEDULER_NAME,
    get_scheduler_runtime_state,
    upsert_scheduler_runtime_state,
)


def _db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def test_upsert_scheduler_runtime_state_records_last_tick_snapshot():
    db = _db()

    row = upsert_scheduler_runtime_state(
        db,
        scheduler_name=AUTO_PICK_SCHEDULER_NAME,
        last_tick_status="OK",
        last_tick_duration_ms=123,
        dry_run=True,
        trading_enabled=False,
        overlap_blocked=False,
        runtime_locked=False,
        last_candidate_symbol="BTCUSDT",
        last_candidate_score="91.5",
        last_execution_mode="dry_run",
    )
    db.commit()

    loaded = get_scheduler_runtime_state(
        db,
        scheduler_name=AUTO_PICK_SCHEDULER_NAME,
    )

    assert row.scheduler_name == AUTO_PICK_SCHEDULER_NAME
    assert loaded is not None
    assert loaded.last_tick_status == "OK"
    assert loaded.last_tick_duration_ms == 123
    assert loaded.dry_run is True
    assert loaded.trading_enabled is False
    assert loaded.overlap_blocked is False
    assert loaded.runtime_locked is False
    assert loaded.last_candidate_symbol == "BTCUSDT"
    assert loaded.last_candidate_score == "91.5"
    assert loaded.last_execution_mode == "dry_run"


def test_upsert_scheduler_runtime_state_replaces_existing_snapshot():
    db = _db()

    upsert_scheduler_runtime_state(
        db,
        scheduler_name=AUTO_PICK_SCHEDULER_NAME,
        last_tick_status="OK",
        dry_run=True,
        trading_enabled=True,
    )
    upsert_scheduler_runtime_state(
        db,
        scheduler_name=AUTO_PICK_SCHEDULER_NAME,
        last_tick_status="OVERLAP_BLOCKED",
        dry_run=False,
        trading_enabled=False,
        overlap_blocked=True,
        runtime_locked=True,
    )
    db.commit()

    rows = db.query(SchedulerRuntimeState).all()
    assert len(rows) == 1

    row = rows[0]
    assert row.last_tick_status == "OVERLAP_BLOCKED"
    assert row.dry_run is False
    assert row.trading_enabled is False
    assert row.overlap_blocked is True
    assert row.runtime_locked is True


def test_scheduler_runtime_state_helpers_record_ok_error_and_overlap():
    from apps.api.app.services.scheduler_runtime_state_service import (
        record_scheduler_overlap_blocked,
        record_scheduler_tick_error,
        record_scheduler_tick_ok,
    )

    db = _db()

    record_scheduler_tick_ok(
        db,
        scheduler_name=AUTO_PICK_SCHEDULER_NAME,
        duration_ms=10,
        dry_run=True,
        trading_enabled=True,
        last_candidate_symbol="BTCUSDT",
        last_candidate_score="90",
        last_execution_mode="dry_run",
    )
    row = get_scheduler_runtime_state(db, scheduler_name=AUTO_PICK_SCHEDULER_NAME)
    assert row.last_tick_status == "OK"
    assert row.overlap_blocked is False
    assert row.runtime_locked is False
    assert row.last_candidate_symbol == "BTCUSDT"

    record_scheduler_tick_error(
        db,
        scheduler_name=AUTO_PICK_SCHEDULER_NAME,
        duration_ms=20,
        dry_run=True,
        trading_enabled=False,
        last_error="boom",
        last_execution_mode="dry_run",
    )
    row = get_scheduler_runtime_state(db, scheduler_name=AUTO_PICK_SCHEDULER_NAME)
    assert row.last_tick_status == "ERROR"
    assert row.last_tick_duration_ms == 20
    assert row.last_error == "boom"
    assert row.overlap_blocked is False
    assert row.runtime_locked is False

    record_scheduler_overlap_blocked(
        db,
        scheduler_name=AUTO_PICK_SCHEDULER_NAME,
        dry_run=True,
        trading_enabled=False,
        last_execution_mode="dry_run",
    )
    row = get_scheduler_runtime_state(db, scheduler_name=AUTO_PICK_SCHEDULER_NAME)
    assert row.last_tick_status == "OVERLAP_BLOCKED"
    assert row.overlap_blocked is True
    assert row.runtime_locked is True
