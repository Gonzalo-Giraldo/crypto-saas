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


def test_runtime_session_local_state_is_stable_per_scheduler_name():
    state_a = runtime_session_identity.get_runtime_session_local_state(
        scheduler_name="auto_pick_internal",
    )
    state_b = runtime_session_identity.get_runtime_session_local_state(
        scheduler_name="auto_pick_internal",
    )

    assert state_a is state_b
    assert state_a.identity.scheduler_name == "auto_pick_internal"


def test_bind_runtime_session_generation_sets_local_generation():
    state = runtime_session_identity.bind_runtime_session_generation(
        scheduler_name="auto_pick_internal",
        runtime_generation=4,
    )

    assert state.runtime_generation == 4


def test_bind_runtime_session_generation_requires_positive_generation():
    try:
        runtime_session_identity.bind_runtime_session_generation(
            scheduler_name="auto_pick_internal",
            runtime_generation=0,
        )
    except ValueError as exc:
        assert str(exc) == "runtime_generation_must_be_positive"
    else:
        raise AssertionError("Expected runtime_generation_must_be_positive")


def test_clear_runtime_session_generation_fails_closed_to_missing_generation():
    runtime_session_identity.bind_runtime_session_generation(
        scheduler_name="auto_pick_internal",
        runtime_generation=5,
    )

    state = runtime_session_identity.clear_runtime_session_generation(
        scheduler_name="auto_pick_internal",
    )

    assert state.runtime_generation is None


def test_bind_runtime_advisory_session_state_sets_local_state():
    from apps.api.app.services.runtime_scheduler.runtime_advisory_session import (
        evaluate_runtime_advisory_session,
    )

    advisory_state = evaluate_runtime_advisory_session(
        acquired=True,
        connection_alive=True,
        lock_still_held=True,
    )

    state = runtime_session_identity.bind_runtime_advisory_session_state(
        scheduler_name="auto_pick_internal",
        advisory_session_state=advisory_state,
    )

    assert state.advisory_session_state.valid is True
    assert state.advisory_session_state.reason is None


def test_clear_runtime_advisory_session_state_fails_closed():
    from apps.api.app.services.runtime_scheduler.runtime_advisory_session import (
        evaluate_runtime_advisory_session,
    )

    runtime_session_identity.bind_runtime_advisory_session_state(
        scheduler_name="auto_pick_internal",
        advisory_session_state=evaluate_runtime_advisory_session(
            acquired=True,
            connection_alive=True,
            lock_still_held=True,
        ),
    )

    state = runtime_session_identity.clear_runtime_advisory_session_state(
        scheduler_name="auto_pick_internal",
    )

    assert state.advisory_session_state.valid is False
    assert state.advisory_session_state.reason == "advisory_session_not_acquired"
