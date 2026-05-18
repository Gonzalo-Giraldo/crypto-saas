from apps.api.app.services.runtime_scheduler.runtime_advisory_session import (
    evaluate_runtime_advisory_session,
)


def test_advisory_session_valid_when_acquired_alive_and_lock_held():
    state = evaluate_runtime_advisory_session(
        acquired=True,
        connection_alive=True,
        lock_still_held=True,
    )

    assert state.acquired is True
    assert state.valid is True
    assert state.reason is None


def test_advisory_session_fails_closed_when_not_acquired():
    state = evaluate_runtime_advisory_session(
        acquired=False,
        connection_alive=True,
        lock_still_held=True,
    )

    assert state.valid is False
    assert state.reason == "advisory_session_not_acquired"


def test_advisory_session_fails_closed_when_connection_lost():
    state = evaluate_runtime_advisory_session(
        acquired=True,
        connection_alive=False,
        lock_still_held=True,
    )

    assert state.valid is False
    assert state.reason == "advisory_session_connection_lost"


def test_advisory_session_fails_closed_when_lock_lost():
    state = evaluate_runtime_advisory_session(
        acquired=True,
        connection_alive=True,
        lock_still_held=False,
    )

    assert state.valid is False
    assert state.reason == "advisory_session_lock_lost"
