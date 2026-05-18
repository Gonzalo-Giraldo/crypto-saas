from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apps.api.app.db.session import Base
from apps.api.app.models.scheduler_runtime_state import SchedulerRuntimeState
from apps.api.app.services.runtime_scheduler.runtime_ownership_atomic_acquisition import (
    atomic_acquire_runtime_ownership,
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


def test_atomic_acquire_runtime_ownership_succeeds_on_empty_state():
    db = _build_db()
    _seed_state(db)

    now = datetime.now(timezone.utc)

    acquired = atomic_acquire_runtime_ownership(
        db,
        scheduler_name="auto_pick_internal",
        runtime_owner_id="owner-a",
        runtime_instance_id="instance-a",
        runtime_generation=1,
        now=now,
    )

    row = db.get(SchedulerRuntimeState, "auto_pick_internal")

    assert acquired is True
    assert row.runtime_owner_id == "owner-a"
    assert row.runtime_instance_id == "instance-a"
    assert row.runtime_generation == 1
    expected_persisted_now = now.replace(tzinfo=None)

    assert row.runtime_started_at == expected_persisted_now
    assert row.runtime_heartbeat_at == expected_persisted_now


def test_atomic_acquire_runtime_ownership_fails_when_already_owned():
    db = _build_db()
    _seed_state(db)

    now = datetime.now(timezone.utc)

    first = atomic_acquire_runtime_ownership(
        db,
        scheduler_name="auto_pick_internal",
        runtime_owner_id="owner-a",
        runtime_instance_id="instance-a",
        runtime_generation=1,
        now=now,
    )

    second = atomic_acquire_runtime_ownership(
        db,
        scheduler_name="auto_pick_internal",
        runtime_owner_id="owner-b",
        runtime_instance_id="instance-b",
        runtime_generation=1,
        now=now,
    )

    row = db.get(SchedulerRuntimeState, "auto_pick_internal")

    assert first is True
    assert second is False
    assert row.runtime_owner_id == "owner-a"
    assert row.runtime_instance_id == "instance-a"


def test_atomic_acquire_runtime_ownership_fails_on_partial_state():
    db = _build_db()
    row = _seed_state(db)
    row.runtime_owner_id = "partial-owner"
    db.flush()

    acquired = atomic_acquire_runtime_ownership(
        db,
        scheduler_name="auto_pick_internal",
        runtime_owner_id="owner-a",
        runtime_instance_id="instance-a",
        runtime_generation=1,
        now=datetime.now(timezone.utc),
    )

    assert acquired is False


def test_atomic_acquire_runtime_ownership_returns_false_for_missing_state():
    db = _build_db()

    acquired = atomic_acquire_runtime_ownership(
        db,
        scheduler_name="missing_scheduler",
        runtime_owner_id="owner-a",
        runtime_instance_id="instance-a",
        runtime_generation=1,
        now=datetime.now(timezone.utc),
    )

    assert acquired is False


def test_atomic_acquire_runtime_ownership_validates_inputs():
    db = _build_db()
    _seed_state(db)

    cases = [
        {
            "scheduler_name": "",
            "runtime_owner_id": "owner",
            "runtime_instance_id": "instance",
            "runtime_generation": 1,
            "now": datetime.now(timezone.utc),
            "error": "scheduler_name_required",
        },
        {
            "scheduler_name": "auto_pick_internal",
            "runtime_owner_id": "",
            "runtime_instance_id": "instance",
            "runtime_generation": 1,
            "now": datetime.now(timezone.utc),
            "error": "runtime_owner_id_required",
        },
        {
            "scheduler_name": "auto_pick_internal",
            "runtime_owner_id": "owner",
            "runtime_instance_id": "",
            "runtime_generation": 1,
            "now": datetime.now(timezone.utc),
            "error": "runtime_instance_id_required",
        },
        {
            "scheduler_name": "auto_pick_internal",
            "runtime_owner_id": "owner",
            "runtime_instance_id": "instance",
            "runtime_generation": 0,
            "now": datetime.now(timezone.utc),
            "error": "runtime_generation_must_be_positive",
        },
        {
            "scheduler_name": "auto_pick_internal",
            "runtime_owner_id": "owner",
            "runtime_instance_id": "instance",
            "runtime_generation": 1,
            "now": datetime.utcnow(),
            "error": "now_must_be_timezone_aware",
        },
    ]

    for case in cases:
        expected_error = case.pop("error")

        try:
            atomic_acquire_runtime_ownership(db, **case)
        except ValueError as exc:
            assert str(exc) == expected_error
        else:
            raise AssertionError(f"Expected {expected_error}")
