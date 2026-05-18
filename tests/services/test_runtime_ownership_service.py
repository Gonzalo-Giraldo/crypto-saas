from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apps.api.app.db.session import Base
from apps.api.app.models.scheduler_runtime_state import SchedulerRuntimeState
from apps.api.app.services.runtime_scheduler.runtime_ownership_service import (
    RuntimeOwnershipAcquireResult,
    acquire_runtime_ownership,
)


def _build_db():
    engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    return TestingSessionLocal()


def _seed_state(db, scheduler_name="auto_pick_internal"):
    row = SchedulerRuntimeState(
        scheduler_name=scheduler_name,
        last_tick_status="OK",
        dry_run=True,
        trading_enabled=False,
    )
    db.add(row)
    db.flush()
    return row


def test_acquire_runtime_ownership_succeeds_on_empty_state():
    db = _build_db()
    row = _seed_state(db)

    result = acquire_runtime_ownership(
        db,
        runtime_state=row,
        now=datetime.now(timezone.utc),
    )

    db.expire_all()
    persisted = db.get(SchedulerRuntimeState, "auto_pick_internal")

    assert isinstance(result, RuntimeOwnershipAcquireResult)
    assert result.acquired is True
    assert result.scheduler_name == "auto_pick_internal"
    assert result.runtime_owner_id is not None
    assert result.runtime_instance_id is not None
    assert result.runtime_generation == 1
    assert result.reason is None

    assert persisted.runtime_owner_id == result.runtime_owner_id
    assert persisted.runtime_instance_id == result.runtime_instance_id
    assert persisted.runtime_generation == 1
    assert persisted.runtime_started_at is not None
    assert persisted.runtime_heartbeat_at is not None


def test_acquire_runtime_ownership_fails_when_already_owned():
    db = _build_db()
    row = _seed_state(db)

    first = acquire_runtime_ownership(
        db,
        runtime_state=row,
        now=datetime.now(timezone.utc),
    )

    db.refresh(row)

    second = acquire_runtime_ownership(
        db,
        runtime_state=row,
        now=datetime.now(timezone.utc),
    )

    assert first.acquired is True
    assert second.acquired is False
    assert second.reason == "ownership_already_present"
    assert second.runtime_owner_id == row.runtime_owner_id
    assert second.runtime_instance_id == row.runtime_instance_id
    assert second.runtime_generation == row.runtime_generation


def test_acquire_runtime_ownership_fails_on_partial_state():
    db = _build_db()
    row = _seed_state(db)

    row.runtime_owner_id = "partial-owner"
    db.flush()

    result = acquire_runtime_ownership(
        db,
        runtime_state=row,
        now=datetime.now(timezone.utc),
    )

    assert result.acquired is False
    assert result.reason == "partial_ownership_state"


def test_acquire_runtime_ownership_fails_closed_when_atomic_update_loses_race():
    db = _build_db()
    row = _seed_state(db)

    other = db.get(SchedulerRuntimeState, "auto_pick_internal")
    other.runtime_owner_id = "winner"
    other.runtime_instance_id = "winner-instance"
    other.runtime_generation = 1
    other.runtime_started_at = datetime.now(timezone.utc)
    other.runtime_heartbeat_at = datetime.now(timezone.utc)
    db.flush()

    stale_view = SchedulerRuntimeState()
    stale_view.scheduler_name = "auto_pick_internal"
    stale_view.runtime_owner_id = None
    stale_view.runtime_instance_id = None
    stale_view.runtime_generation = None
    stale_view.runtime_started_at = None
    stale_view.runtime_heartbeat_at = None

    result = acquire_runtime_ownership(
        db,
        runtime_state=stale_view,
        now=datetime.now(timezone.utc),
    )

    assert result.acquired is False
    assert result.reason == "atomic_acquisition_failed"


def test_acquire_runtime_ownership_uses_next_monotonic_generation_after_clear():
    from apps.api.app.services.scheduler_runtime_state_service import (
        clear_scheduler_runtime_ownership,
    )

    db = _build_db()
    row = _seed_state(db)

    first = acquire_runtime_ownership(
        db,
        runtime_state=row,
        now=datetime.now(timezone.utc),
    )

    assert first.acquired is True
    assert first.runtime_generation == 1

    clear_scheduler_runtime_ownership(
        db,
        scheduler_name="auto_pick_internal",
    )
    db.refresh(row)

    assert row.runtime_generation is None
    assert row.last_runtime_generation == 1

    second = acquire_runtime_ownership(
        db,
        runtime_state=row,
        now=datetime.now(timezone.utc),
    )

    assert second.acquired is True
    assert second.runtime_generation == 2
    assert row.last_runtime_generation == 2


def test_acquire_runtime_ownership_binds_local_runtime_generation_after_success():
    from apps.api.app.services.runtime_scheduler import runtime_session_identity

    runtime_session_identity._runtime_session_identities.clear()
    runtime_session_identity._runtime_session_local_states.clear()

    db = _build_db()
    row = _seed_state(db)

    result = acquire_runtime_ownership(
        db,
        runtime_state=row,
        now=datetime.now(timezone.utc),
    )

    local_state = runtime_session_identity.get_runtime_session_local_state(
        scheduler_name="auto_pick_internal",
    )

    assert result.acquired is True
    assert result.runtime_generation == 1
    assert local_state.runtime_generation == 1


def test_failed_acquire_runtime_ownership_does_not_bind_local_generation():
    from apps.api.app.services.runtime_scheduler import runtime_session_identity

    runtime_session_identity._runtime_session_identities.clear()
    runtime_session_identity._runtime_session_local_states.clear()

    db = _build_db()
    row = _seed_state(db)
    row.runtime_owner_id = "partial-owner"
    db.flush()

    result = acquire_runtime_ownership(
        db,
        runtime_state=row,
        now=datetime.now(timezone.utc),
    )

    local_state = runtime_session_identity.get_runtime_session_local_state(
        scheduler_name="auto_pick_internal",
    )

    assert result.acquired is False
    assert local_state.runtime_generation is None
