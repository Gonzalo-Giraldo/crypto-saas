from datetime import datetime, timezone

from apps.api.app.models.scheduler_runtime_state import (
    SchedulerRuntimeState,
)
from apps.api.app.services.runtime_scheduler.runtime_ownership_validator import (
    RuntimeOwnershipValidationResult,
    validate_runtime_ownership_state,
)


def _build_runtime_state() -> SchedulerRuntimeState:
    row = SchedulerRuntimeState()

    row.scheduler_name = "auto_pick_internal"

    row.runtime_owner_id = None
    row.runtime_instance_id = None
    row.runtime_generation = None
    row.runtime_heartbeat_at = None

    return row


def test_empty_ownership_state_is_valid():
    row = _build_runtime_state()

    result = validate_runtime_ownership_state(
        runtime_state=row,
    )

    assert isinstance(
        result,
        RuntimeOwnershipValidationResult,
    )

    assert result.valid is True
    assert result.reason is None


def test_complete_ownership_state_is_valid():
    row = _build_runtime_state()

    row.runtime_owner_id = "owner-a"
    row.runtime_instance_id = "instance-a"
    row.runtime_generation = 1
    row.runtime_heartbeat_at = datetime.now(timezone.utc)

    result = validate_runtime_ownership_state(
        runtime_state=row,
    )

    assert result.valid is True
    assert result.reason is None


def test_partial_ownership_missing_instance_is_invalid():
    row = _build_runtime_state()

    row.runtime_owner_id = "owner-a"

    result = validate_runtime_ownership_state(
        runtime_state=row,
    )

    assert result.valid is False
    assert result.reason == "partial_ownership_state"


def test_partial_ownership_missing_generation_is_invalid():
    row = _build_runtime_state()

    row.runtime_owner_id = "owner-a"
    row.runtime_instance_id = "instance-a"
    row.runtime_heartbeat_at = datetime.now(timezone.utc)

    result = validate_runtime_ownership_state(
        runtime_state=row,
    )

    assert result.valid is False
    assert result.reason == "partial_ownership_state"


def test_partial_ownership_missing_heartbeat_is_invalid():
    row = _build_runtime_state()

    row.runtime_owner_id = "owner-a"
    row.runtime_instance_id = "instance-a"
    row.runtime_generation = 1

    result = validate_runtime_ownership_state(
        runtime_state=row,
    )

    assert result.valid is False
    assert result.reason == "partial_ownership_state"


def test_runtime_generation_must_be_positive():
    row = _build_runtime_state()

    row.runtime_owner_id = "owner-a"
    row.runtime_instance_id = "instance-a"
    row.runtime_generation = 0
    row.runtime_heartbeat_at = datetime.now(timezone.utc)

    result = validate_runtime_ownership_state(
        runtime_state=row,
    )

    assert result.valid is False
    assert result.reason == "invalid_runtime_generation"
