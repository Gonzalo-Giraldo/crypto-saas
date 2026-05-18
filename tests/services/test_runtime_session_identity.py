from apps.api.app.services.runtime_scheduler import runtime_session_identity
from apps.api.app.services.runtime_scheduler.runtime_session_identity import (
    get_runtime_session_identity,
)


def setup_function():
    runtime_session_identity._runtime_session_identities.clear()


def test_runtime_session_identity_is_stable_per_scheduler_name():
    identity_a = get_runtime_session_identity(
        scheduler_name="auto_pick_internal",
    )
    identity_b = get_runtime_session_identity(
        scheduler_name="auto_pick_internal",
    )

    assert identity_a == identity_b
    assert identity_a.runtime_instance_id == identity_b.runtime_instance_id


def test_runtime_session_identity_is_distinct_per_scheduler_name():
    identity_a = get_runtime_session_identity(
        scheduler_name="auto_pick_internal",
    )
    identity_b = get_runtime_session_identity(
        scheduler_name="other_scheduler",
    )

    assert identity_a.scheduler_name == "auto_pick_internal"
    assert identity_b.scheduler_name == "other_scheduler"
    assert identity_a.runtime_owner_id != identity_b.runtime_owner_id
    assert identity_a.runtime_instance_id != identity_b.runtime_instance_id


def test_runtime_session_identity_requires_scheduler_name():
    try:
        get_runtime_session_identity(
            scheduler_name="",
        )
    except ValueError as exc:
        assert str(exc) == "scheduler_name_required"
    else:
        raise AssertionError("Expected scheduler_name_required")
