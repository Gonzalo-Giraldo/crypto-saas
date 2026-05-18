from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apps.api.app.db.session import Base
from apps.api.app.models.scheduler_runtime_state import (
    SchedulerRuntimeState,
)
from apps.api.app.services.scheduler_runtime_state_service import (
    upsert_scheduler_runtime_state,
)


def _build_db():
    engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(bind=engine)

    Base.metadata.create_all(bind=engine)

    return TestingSessionLocal()


def test_runtime_ownership_fields_are_optional():
    db = _build_db()

    row = upsert_scheduler_runtime_state(
        db,
        scheduler_name="test_scheduler",
        last_tick_status="OK",
        dry_run=True,
        trading_enabled=False,
    )

    assert isinstance(row, SchedulerRuntimeState)

    assert row.runtime_owner_id is None
    assert row.runtime_instance_id is None
    assert row.runtime_generation is None
    assert row.runtime_started_at is None
    assert row.runtime_heartbeat_at is None


def test_runtime_ownership_fields_can_be_persisted():
    db = _build_db()

    started_at = datetime.now(timezone.utc)
    heartbeat_at = datetime.now(timezone.utc)

    row = upsert_scheduler_runtime_state(
        db,
        scheduler_name="test_scheduler",
        last_tick_status="OK",
        dry_run=True,
        trading_enabled=False,
        runtime_owner_id="owner-a",
        runtime_instance_id="instance-a",
        runtime_generation=1,
        runtime_started_at=started_at,
        runtime_heartbeat_at=heartbeat_at,
    )

    assert row.runtime_owner_id == "owner-a"
    assert row.runtime_instance_id == "instance-a"
    assert row.runtime_generation == 1
    assert row.runtime_started_at == started_at
    assert row.runtime_heartbeat_at == heartbeat_at


def test_runtime_locked_semantics_remain_unchanged():
    db = _build_db()

    row = upsert_scheduler_runtime_state(
        db,
        scheduler_name="test_scheduler",
        last_tick_status="OVERLAP_BLOCKED",
        dry_run=True,
        trading_enabled=False,
        runtime_locked=True,
    )

    assert row.runtime_locked is True

    assert row.runtime_owner_id is None
    assert row.runtime_instance_id is None


from apps.api.app.services.scheduler_runtime_state_service import (
    clear_scheduler_runtime_ownership,
    update_scheduler_runtime_ownership,
)


def test_update_scheduler_runtime_ownership():
    db = _build_db()

    upsert_scheduler_runtime_state(
        db,
        scheduler_name="test_scheduler",
        last_tick_status="OK",
        dry_run=True,
        trading_enabled=False,
    )

    started_at = datetime.now(timezone.utc)
    heartbeat_at = datetime.now(timezone.utc)

    row = update_scheduler_runtime_ownership(
        db,
        scheduler_name="test_scheduler",
        runtime_owner_id="owner-b",
        runtime_instance_id="instance-b",
        runtime_generation=2,
        runtime_started_at=started_at,
        runtime_heartbeat_at=heartbeat_at,
    )

    assert row.runtime_owner_id == "owner-b"
    assert row.runtime_instance_id == "instance-b"
    assert row.runtime_generation == 2
    assert row.runtime_started_at == started_at
    assert row.runtime_heartbeat_at == heartbeat_at


def test_clear_scheduler_runtime_ownership():
    db = _build_db()

    started_at = datetime.now(timezone.utc)
    heartbeat_at = datetime.now(timezone.utc)

    upsert_scheduler_runtime_state(
        db,
        scheduler_name="test_scheduler",
        last_tick_status="OK",
        dry_run=True,
        trading_enabled=False,
        runtime_owner_id="owner-c",
        runtime_instance_id="instance-c",
        runtime_generation=3,
        runtime_started_at=started_at,
        runtime_heartbeat_at=heartbeat_at,
    )

    row = clear_scheduler_runtime_ownership(
        db,
        scheduler_name="test_scheduler",
    )

    assert row.runtime_owner_id is None
    assert row.runtime_instance_id is None
    assert row.runtime_generation is None
    assert row.runtime_started_at is None
    assert row.runtime_heartbeat_at is None


def test_update_scheduler_runtime_ownership_requires_existing_state():
    db = _build_db()

    try:
        update_scheduler_runtime_ownership(
            db,
            scheduler_name="missing_scheduler",
            runtime_owner_id="owner",
            runtime_instance_id="instance",
            runtime_generation=1,
            runtime_started_at=datetime.now(timezone.utc),
            runtime_heartbeat_at=datetime.now(timezone.utc),
        )
    except ValueError as exc:
        assert str(exc) == "scheduler_runtime_state_not_found"
    else:
        raise AssertionError("Expected scheduler_runtime_state_not_found")


def test_clear_scheduler_runtime_ownership_requires_existing_state():
    db = _build_db()

    try:
        clear_scheduler_runtime_ownership(
            db,
            scheduler_name="missing_scheduler",
        )
    except ValueError as exc:
        assert str(exc) == "scheduler_runtime_state_not_found"
    else:
        raise AssertionError("Expected scheduler_runtime_state_not_found")


from apps.api.app.services.scheduler_runtime_state_service import (
    touch_scheduler_runtime_heartbeat,
)


def test_touch_scheduler_runtime_heartbeat():
    db = _build_db()

    upsert_scheduler_runtime_state(
        db,
        scheduler_name="test_scheduler",
        last_tick_status="OK",
        dry_run=True,
        trading_enabled=False,
    )

    heartbeat_at = datetime.now(timezone.utc)

    row = touch_scheduler_runtime_heartbeat(
        db,
        scheduler_name="test_scheduler",
        runtime_heartbeat_at=heartbeat_at,
    )

    assert row.runtime_heartbeat_at == heartbeat_at


def test_touch_scheduler_runtime_heartbeat_requires_existing_state():
    db = _build_db()

    try:
        touch_scheduler_runtime_heartbeat(
            db,
            scheduler_name="missing_scheduler",
            runtime_heartbeat_at=datetime.now(timezone.utc),
        )
    except ValueError as exc:
        assert str(exc) == "scheduler_runtime_state_not_found"
    else:
        raise AssertionError("Expected scheduler_runtime_state_not_found")
