from datetime import datetime, timedelta, timezone

from apps.api.app.models.scheduler_runtime_state import (
    SchedulerRuntimeState,
)
from apps.api.app.services.runtime_scheduler.runtime_ownership_lifecycle import (
    RuntimeOwnershipLifecycleState,
    build_runtime_ownership_lifecycle_projection,
)


def _build_runtime_state() -> SchedulerRuntimeState:
    row = SchedulerRuntimeState()
    row.scheduler_name = "auto_pick_internal"
    row.runtime_owner_id = None
    row.runtime_instance_id = None
    row.runtime_generation = None
    row.runtime_heartbeat_at = None
    return row


def test_lifecycle_projection_returns_init_when_ownership_absent():
    row = _build_runtime_state()

    projection = build_runtime_ownership_lifecycle_projection(
        runtime_state=row,
        stale_after_seconds=60,
    )

    assert projection.state == RuntimeOwnershipLifecycleState.INIT
    assert projection.valid_ownership is True
    assert projection.stale is False
    assert projection.operator_attention_required is False
    assert projection.reason == "ownership_not_present"


def test_lifecycle_projection_returns_active_when_owned_and_fresh():
    row = _build_runtime_state()
    row.runtime_owner_id = "owner"
    row.runtime_instance_id = "instance"
    row.runtime_generation = 1
    row.runtime_heartbeat_at = datetime.now(timezone.utc)

    projection = build_runtime_ownership_lifecycle_projection(
        runtime_state=row,
        stale_after_seconds=60,
    )

    assert projection.state == RuntimeOwnershipLifecycleState.ACTIVE
    assert projection.valid_ownership is True
    assert projection.stale is False
    assert projection.operator_attention_required is False
    assert projection.reason is None


def test_lifecycle_projection_returns_stale_when_owned_and_heartbeat_stale():
    row = _build_runtime_state()
    row.runtime_owner_id = "owner"
    row.runtime_instance_id = "instance"
    row.runtime_generation = 1
    row.runtime_heartbeat_at = (
        datetime.now(timezone.utc) - timedelta(seconds=61)
    )

    projection = build_runtime_ownership_lifecycle_projection(
        runtime_state=row,
        stale_after_seconds=60,
    )

    assert projection.state == RuntimeOwnershipLifecycleState.STALE
    assert projection.valid_ownership is True
    assert projection.stale is True
    assert projection.operator_attention_required is True
    assert projection.reason == "runtime_heartbeat_stale"


def test_lifecycle_projection_fails_closed_on_partial_ownership():
    row = _build_runtime_state()
    row.runtime_owner_id = "owner"

    projection = build_runtime_ownership_lifecycle_projection(
        runtime_state=row,
        stale_after_seconds=60,
    )

    assert projection.state == RuntimeOwnershipLifecycleState.FAILED
    assert projection.valid_ownership is False
    assert projection.stale is True
    assert projection.operator_attention_required is True
    assert projection.reason == "partial_ownership_state"


def test_lifecycle_projection_fails_closed_on_invalid_generation():
    row = _build_runtime_state()
    row.runtime_owner_id = "owner"
    row.runtime_instance_id = "instance"
    row.runtime_generation = 0
    row.runtime_heartbeat_at = datetime.now(timezone.utc)

    projection = build_runtime_ownership_lifecycle_projection(
        runtime_state=row,
        stale_after_seconds=60,
    )

    assert projection.state == RuntimeOwnershipLifecycleState.FAILED
    assert projection.valid_ownership is False
    assert projection.stale is True
    assert projection.operator_attention_required is True
    assert projection.reason == "invalid_runtime_generation"


def test_active_lifecycle_projection_is_not_durable_runtime_authority():
    row = _build_runtime_state()
    row.runtime_owner_id = "owner"
    row.runtime_instance_id = "instance"
    row.runtime_generation = 1
    row.runtime_heartbeat_at = datetime.now(timezone.utc)

    projection = build_runtime_ownership_lifecycle_projection(
        runtime_state=row,
        stale_after_seconds=60,
    )

    assert projection.state == RuntimeOwnershipLifecycleState.ACTIVE

    # ACTIVE here is an observability projection only.
    # It does not prove durable advisory/session lock authority.
    # It does not prove local runtime process authority.
    # It does not prove ownership-to-lock reconciliation.
    # It must not be used as execution authority or broker mutation authority.
    assert projection.valid_ownership is True
    assert projection.operator_attention_required is False
