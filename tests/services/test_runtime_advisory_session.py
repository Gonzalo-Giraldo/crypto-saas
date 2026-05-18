from apps.api.app.services.runtime_scheduler.runtime_advisory_session import (
    AUTO_PICK_RUNTIME_SESSION_LOCK_KEY,
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


def test_runtime_session_lock_key_is_separate_from_tick_lock_key():
    assert AUTO_PICK_RUNTIME_SESSION_LOCK_KEY == 887732
    assert AUTO_PICK_RUNTIME_SESSION_LOCK_KEY != 887731


def test_runtime_advisory_session_starts_fail_closed():
    from apps.api.app.services.runtime_scheduler.runtime_advisory_session import (
        RuntimeAdvisorySession,
    )

    session = RuntimeAdvisorySession()

    state = session.current_state()

    assert state.valid is False
    assert state.reason == "advisory_session_not_acquired"


def test_runtime_advisory_session_marks_acquired_state_valid():
    from apps.api.app.services.runtime_scheduler.runtime_advisory_session import (
        RuntimeAdvisorySession,
    )

    session = RuntimeAdvisorySession()
    session.mark_acquired()

    state = session.current_state()

    assert state.valid is True
    assert state.reason is None


def test_runtime_advisory_session_connection_loss_fails_closed():
    from apps.api.app.services.runtime_scheduler.runtime_advisory_session import (
        RuntimeAdvisorySession,
    )

    session = RuntimeAdvisorySession()
    session.mark_acquired()
    session.mark_connection_lost()

    state = session.current_state()

    assert state.valid is False
    assert state.reason == "advisory_session_connection_lost"


def test_runtime_advisory_session_release_fails_closed():
    from apps.api.app.services.runtime_scheduler.runtime_advisory_session import (
        RuntimeAdvisorySession,
    )

    session = RuntimeAdvisorySession()
    session.mark_acquired()
    session.mark_released()

    state = session.current_state()

    assert state.valid is False
    assert state.reason == "advisory_session_not_acquired"


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


def test_runtime_advisory_session_lock_acquires_on_dedicated_connection():
    from apps.api.app.services.runtime_scheduler.runtime_advisory_session import (
        RuntimeAdvisorySessionLock,
    )

    connection = _FakeConnection(acquire_result=True)
    lock = RuntimeAdvisorySessionLock(engine=_FakeEngine(connection))

    state = lock.acquire()

    assert state.valid is True
    assert connection.closed is False
    assert any("pg_try_advisory_lock" in sql for sql, _ in connection.statements)


def test_runtime_advisory_session_lock_fails_closed_when_not_acquired():
    from apps.api.app.services.runtime_scheduler.runtime_advisory_session import (
        RuntimeAdvisorySessionLock,
    )

    connection = _FakeConnection(acquire_result=False)
    lock = RuntimeAdvisorySessionLock(engine=_FakeEngine(connection))

    state = lock.acquire()

    assert state.valid is False
    assert state.reason == "advisory_session_not_acquired"
    assert connection.closed is True


def test_runtime_advisory_session_lock_release_unlocks_and_fails_closed():
    from apps.api.app.services.runtime_scheduler.runtime_advisory_session import (
        RuntimeAdvisorySessionLock,
    )

    connection = _FakeConnection(acquire_result=True)
    lock = RuntimeAdvisorySessionLock(engine=_FakeEngine(connection))

    acquired = lock.acquire()
    released = lock.release()

    assert acquired.valid is True
    assert released.valid is False
    assert released.reason == "advisory_session_not_acquired"
    assert connection.closed is True
    assert any("pg_advisory_unlock" in sql for sql, _ in connection.statements)


def test_runtime_advisory_session_lock_connection_failure_fails_closed():
    from apps.api.app.services.runtime_scheduler.runtime_advisory_session import (
        RuntimeAdvisorySessionLock,
    )

    connection = _FakeConnection(acquire_result=True)
    lock = RuntimeAdvisorySessionLock(engine=_FakeEngine(connection))

    acquired = lock.acquire()
    connection.fail_on_execute = True
    state = lock.current_state()

    assert acquired.valid is True
    assert state.valid is False
    assert state.reason == "advisory_session_connection_lost"
    assert connection.closed is True
