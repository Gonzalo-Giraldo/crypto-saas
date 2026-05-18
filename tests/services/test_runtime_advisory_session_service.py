from apps.api.app.services.runtime_scheduler import runtime_session_identity
from apps.api.app.services.runtime_scheduler.runtime_advisory_session_service import (
    acquire_runtime_advisory_session,
    release_runtime_advisory_session,
)


class _FakeScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar(self):
        return self._value


class _FakeConnection:
    def __init__(self, *, acquire_result=True, fail_on_execute=False):
        self.acquire_result = acquire_result
        self.fail_on_execute = fail_on_execute
        self.closed = False
        self.statements = []

    def execute(self, statement, params=None):
        if self.fail_on_execute:
            raise RuntimeError("connection_failed")

        sql = str(statement)
        self.statements.append((sql, params or {}))

        if "pg_try_advisory_lock" in sql:
            return _FakeScalarResult(self.acquire_result)

        if "pg_advisory_unlock" in sql:
            return _FakeScalarResult(True)

        return _FakeScalarResult(1)

    def close(self):
        self.closed = True


class _FakeEngine:
    def __init__(self, connection):
        self.connection = connection
        self.connect_calls = 0

    def connect(self):
        self.connect_calls += 1
        return self.connection


def setup_function():
    runtime_session_identity._runtime_session_identities.clear()
    runtime_session_identity._runtime_session_local_states.clear()


def test_acquire_runtime_advisory_session_binds_valid_local_state():
    connection = _FakeConnection(acquire_result=True)

    result = acquire_runtime_advisory_session(
        engine=_FakeEngine(connection),
        scheduler_name="auto_pick_internal",
    )

    local_state = runtime_session_identity.get_runtime_session_local_state(
        scheduler_name="auto_pick_internal",
    )

    assert result.state.valid is True
    assert result.lock is not None
    assert local_state.advisory_session_state.valid is True
    assert connection.closed is False


def test_acquire_runtime_advisory_session_fails_closed_when_lock_not_acquired():
    connection = _FakeConnection(acquire_result=False)

    result = acquire_runtime_advisory_session(
        engine=_FakeEngine(connection),
        scheduler_name="auto_pick_internal",
    )

    local_state = runtime_session_identity.get_runtime_session_local_state(
        scheduler_name="auto_pick_internal",
    )

    assert result.state.valid is False
    assert result.state.reason == "advisory_session_not_acquired"
    assert result.lock is None
    assert local_state.advisory_session_state.valid is False
    assert local_state.advisory_session_state.reason == "advisory_session_not_acquired"
    assert connection.closed is True


def test_release_runtime_advisory_session_unlocks_and_clears_local_state():
    connection = _FakeConnection(acquire_result=True)

    result = acquire_runtime_advisory_session(
        engine=_FakeEngine(connection),
        scheduler_name="auto_pick_internal",
    )

    release_state = release_runtime_advisory_session(
        scheduler_name="auto_pick_internal",
        lock=result.lock,
    )

    local_state = runtime_session_identity.get_runtime_session_local_state(
        scheduler_name="auto_pick_internal",
    )

    assert release_state.valid is False
    assert release_state.reason == "advisory_session_not_acquired"
    assert local_state.advisory_session_state.valid is False
    assert local_state.advisory_session_state.reason == "advisory_session_not_acquired"
    assert any("pg_advisory_unlock" in sql for sql, _ in connection.statements)
    assert connection.closed is True


def test_release_runtime_advisory_session_without_lock_clears_local_state():
    state = release_runtime_advisory_session(
        scheduler_name="auto_pick_internal",
        lock=None,
    )

    local_state = runtime_session_identity.get_runtime_session_local_state(
        scheduler_name="auto_pick_internal",
    )

    assert state.valid is False
    assert state.reason == "advisory_session_not_acquired"
    assert local_state.advisory_session_state.valid is False
