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
    assert row.runtime_heartbeat_at.replace(tzinfo=timezone.utc) == heartbeat_at


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


from apps.api.app.services.scheduler_runtime_state_service import (
    touch_scheduler_runtime_heartbeat_owned,
)


def test_touch_scheduler_runtime_heartbeat_owned_requires_matching_owner_identity_and_generation():
    db = _build_db()

    started_at = datetime.now(timezone.utc)
    initial_heartbeat_at = datetime.now(timezone.utc)

    upsert_scheduler_runtime_state(
        db,
        scheduler_name="test_scheduler",
        last_tick_status="OK",
        dry_run=True,
        trading_enabled=False,
        runtime_owner_id="owner-d",
        runtime_instance_id="instance-d",
        runtime_generation=4,
        runtime_started_at=started_at,
        runtime_heartbeat_at=initial_heartbeat_at,
    )

    heartbeat_at = datetime.now(timezone.utc)

    row = touch_scheduler_runtime_heartbeat_owned(
        db,
        scheduler_name="test_scheduler",
        runtime_owner_id="owner-d",
        runtime_instance_id="instance-d",
        runtime_generation=4,
        runtime_heartbeat_at=heartbeat_at,
    )

    assert row.runtime_heartbeat_at.replace(tzinfo=timezone.utc) == heartbeat_at


def test_touch_scheduler_runtime_heartbeat_owned_fails_closed_on_owner_mismatch():
    db = _build_db()

    initial_heartbeat_at = datetime.now(timezone.utc)

    upsert_scheduler_runtime_state(
        db,
        scheduler_name="test_scheduler",
        last_tick_status="OK",
        dry_run=True,
        trading_enabled=False,
        runtime_owner_id="owner-e",
        runtime_instance_id="instance-e",
        runtime_generation=5,
        runtime_started_at=initial_heartbeat_at,
        runtime_heartbeat_at=initial_heartbeat_at,
    )

    try:
        touch_scheduler_runtime_heartbeat_owned(
            db,
            scheduler_name="test_scheduler",
            runtime_owner_id="wrong-owner",
            runtime_instance_id="instance-e",
            runtime_generation=5,
            runtime_heartbeat_at=datetime.now(timezone.utc),
        )
    except ValueError as exc:
        assert str(exc) == "runtime_heartbeat_owner_mismatch"
    else:
        raise AssertionError("Expected runtime_heartbeat_owner_mismatch")


def test_touch_scheduler_runtime_heartbeat_owned_fails_closed_on_generation_mismatch():
    db = _build_db()

    initial_heartbeat_at = datetime.now(timezone.utc)

    upsert_scheduler_runtime_state(
        db,
        scheduler_name="test_scheduler",
        last_tick_status="OK",
        dry_run=True,
        trading_enabled=False,
        runtime_owner_id="owner-f",
        runtime_instance_id="instance-f",
        runtime_generation=6,
        runtime_started_at=initial_heartbeat_at,
        runtime_heartbeat_at=initial_heartbeat_at,
    )

    try:
        touch_scheduler_runtime_heartbeat_owned(
            db,
            scheduler_name="test_scheduler",
            runtime_owner_id="owner-f",
            runtime_instance_id="instance-f",
            runtime_generation=7,
            runtime_heartbeat_at=datetime.now(timezone.utc),
        )
    except ValueError as exc:
        assert str(exc) == "runtime_heartbeat_owner_mismatch"
    else:
        raise AssertionError("Expected runtime_heartbeat_owner_mismatch")


def test_touch_scheduler_runtime_heartbeat_owned_requires_timezone_aware_heartbeat():
    db = _build_db()

    try:
        touch_scheduler_runtime_heartbeat_owned(
            db,
            scheduler_name="test_scheduler",
            runtime_owner_id="owner-g",
            runtime_instance_id="instance-g",
            runtime_generation=1,
            runtime_heartbeat_at=datetime.utcnow(),
        )
    except ValueError as exc:
        assert str(exc) == "runtime_heartbeat_at_must_be_timezone_aware"
    else:
        raise AssertionError("Expected runtime_heartbeat_at_must_be_timezone_aware")


def test_clear_scheduler_runtime_ownership_owned_requires_matching_owner_identity_and_generation():
    from datetime import datetime, timezone

    from apps.api.app.models.scheduler_runtime_state import SchedulerRuntimeState
    from apps.api.app.services.scheduler_runtime_state_service import (
        clear_scheduler_runtime_ownership_owned,
    )

    db = _build_db()
    heartbeat_at = datetime.now(timezone.utc)

    row = SchedulerRuntimeState(
        scheduler_name="auto_pick_internal",
        runtime_owner_id="owner-owned",
        runtime_instance_id="instance-owned",
        runtime_generation=9,
        runtime_started_at=heartbeat_at,
        runtime_heartbeat_at=heartbeat_at,
    )
    db.add(row)
    db.commit()

    cleared = clear_scheduler_runtime_ownership_owned(
        db,
        scheduler_name="auto_pick_internal",
        runtime_owner_id="owner-owned",
        runtime_instance_id="instance-owned",
        runtime_generation=9,
    )

    assert cleared.runtime_owner_id is None
    assert cleared.runtime_instance_id is None
    assert cleared.runtime_generation is None
    assert cleared.runtime_started_at is None
    assert cleared.runtime_heartbeat_at is None


def test_clear_scheduler_runtime_ownership_owned_fails_closed_on_owner_mismatch():
    from datetime import datetime, timezone

    from apps.api.app.models.scheduler_runtime_state import SchedulerRuntimeState
    from apps.api.app.services.scheduler_runtime_state_service import (
        clear_scheduler_runtime_ownership_owned,
    )

    db = _build_db()
    heartbeat_at = datetime.now(timezone.utc)

    row = SchedulerRuntimeState(
        scheduler_name="auto_pick_internal",
        runtime_owner_id="owner-real",
        runtime_instance_id="instance-real",
        runtime_generation=10,
        runtime_started_at=heartbeat_at,
        runtime_heartbeat_at=heartbeat_at,
    )
    db.add(row)
    db.commit()

    try:
        clear_scheduler_runtime_ownership_owned(
            db,
            scheduler_name="auto_pick_internal",
            runtime_owner_id="wrong-owner",
            runtime_instance_id="instance-real",
            runtime_generation=10,
        )
    except ValueError as exc:
        assert str(exc) == "runtime_ownership_owner_mismatch"
    else:
        raise AssertionError("Expected runtime_ownership_owner_mismatch")

    persisted = db.get(SchedulerRuntimeState, "auto_pick_internal")
    assert persisted.runtime_owner_id == "owner-real"
    assert persisted.runtime_instance_id == "instance-real"
    assert persisted.runtime_generation == 10


def test_clear_scheduler_runtime_ownership_owned_fails_closed_on_generation_mismatch():
    from datetime import datetime, timezone

    from apps.api.app.models.scheduler_runtime_state import SchedulerRuntimeState
    from apps.api.app.services.scheduler_runtime_state_service import (
        clear_scheduler_runtime_ownership_owned,
    )

    db = _build_db()
    heartbeat_at = datetime.now(timezone.utc)

    row = SchedulerRuntimeState(
        scheduler_name="auto_pick_internal",
        runtime_owner_id="owner-gen",
        runtime_instance_id="instance-gen",
        runtime_generation=11,
        runtime_started_at=heartbeat_at,
        runtime_heartbeat_at=heartbeat_at,
    )
    db.add(row)
    db.commit()

    try:
        clear_scheduler_runtime_ownership_owned(
            db,
            scheduler_name="auto_pick_internal",
            runtime_owner_id="owner-gen",
            runtime_instance_id="instance-gen",
            runtime_generation=12,
        )
    except ValueError as exc:
        assert str(exc) == "runtime_ownership_owner_mismatch"
    else:
        raise AssertionError("Expected runtime_ownership_owner_mismatch")

    persisted = db.get(SchedulerRuntimeState, "auto_pick_internal")
    assert persisted.runtime_owner_id == "owner-gen"
    assert persisted.runtime_instance_id == "instance-gen"
    assert persisted.runtime_generation == 11
