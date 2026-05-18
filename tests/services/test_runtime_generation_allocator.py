from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apps.api.app.db.session import Base
from apps.api.app.models.scheduler_runtime_state import SchedulerRuntimeState
from apps.api.app.services.runtime_scheduler.runtime_generation_allocator import (
    allocate_next_runtime_generation,
)


def _build_db():
    engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    return TestingSessionLocal()


def _seed_state(db, *, scheduler_name="auto_pick_internal", last_runtime_generation=0):
    row = SchedulerRuntimeState(
        scheduler_name=scheduler_name,
        last_tick_status="OK",
        dry_run=True,
        trading_enabled=False,
        last_runtime_generation=last_runtime_generation,
    )
    db.add(row)
    db.flush()
    return row


def test_allocate_next_runtime_generation_starts_at_one():
    db = _build_db()
    row = _seed_state(db)

    assert allocate_next_runtime_generation(
        db,
        scheduler_name="auto_pick_internal",
    ) == 1

    db.refresh(row)
    assert row.last_runtime_generation == 1


def test_allocate_next_runtime_generation_increments_existing_generation():
    db = _build_db()
    row = _seed_state(db, last_runtime_generation=7)

    assert allocate_next_runtime_generation(
        db,
        scheduler_name="auto_pick_internal",
    ) == 8

    db.refresh(row)
    assert row.last_runtime_generation == 8


def test_allocate_next_runtime_generation_requires_existing_state():
    db = _build_db()

    try:
        allocate_next_runtime_generation(
            db,
            scheduler_name="missing_scheduler",
        )
    except ValueError as exc:
        assert str(exc) == "scheduler_runtime_state_not_found"
    else:
        raise AssertionError("Expected scheduler_runtime_state_not_found")


def test_allocate_next_runtime_generation_rejects_negative_generation():
    db = _build_db()
    _seed_state(db, last_runtime_generation=-1)

    try:
        allocate_next_runtime_generation(
            db,
            scheduler_name="auto_pick_internal",
        )
    except ValueError as exc:
        assert str(exc) == "runtime_generation_must_not_be_negative"
    else:
        raise AssertionError("Expected runtime_generation_must_not_be_negative")
