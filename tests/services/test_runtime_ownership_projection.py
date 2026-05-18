from datetime import datetime, timedelta, timezone

from apps.api.app.models.scheduler_runtime_state import (
    SchedulerRuntimeState,
)
from apps.api.app.services.runtime_scheduler.runtime_ownership_projection import (
    RuntimeOwnershipProjection,
    build_runtime_ownership_projection,
)


def _build_runtime_state() -> SchedulerRuntimeState:
    row = SchedulerRuntimeState()

    row.scheduler_name = "auto_pick_internal"

    row.runtime_owner_id = None
    row.runtime_instance_id = None
    row.runtime_generation = None

    row.runtime_started_at = None
    row.runtime_heartbeat_at = None

    row.runtime_locked = False
    row.trading_enabled = False
    row.dry_run = True

    return row


def test_projection_without_ownership():
    row = _build_runtime_state()

    projection = build_runtime_ownership_projection(
        runtime_state=row,
        now=datetime.now(timezone.utc),
    )

    assert isinstance(
        projection,
        RuntimeOwnershipProjection,
    )

    assert projection.ownership_present is False
    assert projection.heartbeat_stale is True


def test_projection_with_valid_ownership():
    row = _build_runtime_state()

    now = datetime.now(timezone.utc)

    row.runtime_owner_id = "owner-a"
    row.runtime_instance_id = "instance-a"
    row.runtime_generation = 1
    row.runtime_started_at = now
    row.runtime_heartbeat_at = now

    projection = build_runtime_ownership_projection(
        runtime_state=row,
        now=now,
    )

    assert projection.ownership_present is True
    assert projection.heartbeat_stale is False

    assert projection.runtime_owner_id == "owner-a"
    assert projection.runtime_instance_id == "instance-a"
    assert projection.runtime_generation == 1


def test_projection_detects_stale_heartbeat():
    row = _build_runtime_state()

    now = datetime.now(timezone.utc)

    row.runtime_owner_id = "owner-a"
    row.runtime_instance_id = "instance-a"

    row.runtime_heartbeat_at = (
        now - timedelta(seconds=120)
    )

    projection = build_runtime_ownership_projection(
        runtime_state=row,
        now=now,
        stale_timeout_seconds=60,
    )

    assert projection.heartbeat_stale is True


def test_projection_preserves_runtime_flags():
    row = _build_runtime_state()

    row.runtime_locked = True
    row.trading_enabled = True
    row.dry_run = False

    projection = build_runtime_ownership_projection(
        runtime_state=row,
        now=datetime.now(timezone.utc),
    )

    assert projection.runtime_locked is True
    assert projection.trading_enabled is True
    assert projection.dry_run is False


def test_projection_is_frozen():
    row = _build_runtime_state()

    projection = build_runtime_ownership_projection(
        runtime_state=row,
        now=datetime.now(timezone.utc),
    )

    try:
        projection.runtime_locked = True
    except Exception:
        pass
    else:
        raise AssertionError(
            "Projection should be immutable"
        )
