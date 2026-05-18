from apps.api.app.services.runtime_scheduler import runtime_session_identity
from apps.api.app.services.runtime_scheduler.runtime_advisory_session_service import (
    acquire_runtime_advisory_session,
)
from apps.api.app.services.runtime_scheduler.runtime_authority_snapshot import (
    refresh_runtime_authority_snapshot,
)
from apps.api.app.services.runtime_scheduler.runtime_authority_state import (
    RuntimeAuthorityState,
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

    def connect(self):
        return self.connection


def setup_function():
    runtime_session_identity._runtime_session_identities.clear()
    runtime_session_identity._runtime_session_local_states.clear()


def test_runtime_authority_snapshot_active_when_all_evidence_is_valid():
    connection = _FakeConnection(acquire_result=True)
    acquired = acquire_runtime_advisory_session(
        engine=_FakeEngine(connection),
        scheduler_name="auto_pick_internal",
    )

    snapshot = refresh_runtime_authority_snapshot(
        scheduler_name="auto_pick_internal",
        advisory_lock=acquired.lock,
        ownership_row_present=True,
        local_identity_matches=True,
        local_runtime_generation=2,
        durable_runtime_generation=2,
        heartbeat_fresh=True,
        runtime_health_valid=True,
    )

    assert snapshot.advisory_session.valid is True
    assert snapshot.generation_reconciliation.matches is True
    assert snapshot.authority.valid is True
    assert snapshot.authority_state.state == RuntimeAuthorityState.ACTIVE


def test_runtime_authority_snapshot_lost_lock_when_advisory_connection_lost():
    connection = _FakeConnection(acquire_result=True)
    acquired = acquire_runtime_advisory_session(
        engine=_FakeEngine(connection),
        scheduler_name="auto_pick_internal",
    )

    connection.fail_on_execute = True

    snapshot = refresh_runtime_authority_snapshot(
        scheduler_name="auto_pick_internal",
        advisory_lock=acquired.lock,
        ownership_row_present=True,
        local_identity_matches=True,
        local_runtime_generation=2,
        durable_runtime_generation=2,
        heartbeat_fresh=True,
        runtime_health_valid=True,
    )

    assert snapshot.advisory_session.valid is False
    assert snapshot.advisory_session.reason == "advisory_session_connection_lost"
    assert snapshot.authority.valid is False
    assert snapshot.authority.reason == "advisory_session_not_valid"
    assert snapshot.authority_state.state == RuntimeAuthorityState.LOST_LOCK


def test_runtime_authority_snapshot_generation_mismatch_fails_closed():
    connection = _FakeConnection(acquire_result=True)
    acquired = acquire_runtime_advisory_session(
        engine=_FakeEngine(connection),
        scheduler_name="auto_pick_internal",
    )

    snapshot = refresh_runtime_authority_snapshot(
        scheduler_name="auto_pick_internal",
        advisory_lock=acquired.lock,
        ownership_row_present=True,
        local_identity_matches=True,
        local_runtime_generation=1,
        durable_runtime_generation=2,
        heartbeat_fresh=True,
        runtime_health_valid=True,
    )

    assert snapshot.generation_reconciliation.matches is False
    assert snapshot.generation_reconciliation.reason == "runtime_generation_mismatch"
    assert snapshot.authority.valid is False
    assert snapshot.authority.reason == "runtime_generation_mismatch"
    assert snapshot.authority_state.state == RuntimeAuthorityState.GENERATION_MISMATCH


def test_runtime_authority_snapshot_without_advisory_lock_stays_init():
    snapshot = refresh_runtime_authority_snapshot(
        scheduler_name="auto_pick_internal",
        advisory_lock=None,
        ownership_row_present=False,
        local_identity_matches=False,
        local_runtime_generation=None,
        durable_runtime_generation=None,
        heartbeat_fresh=False,
        runtime_health_valid=False,
    )

    assert snapshot.advisory_session.valid is False
    assert snapshot.advisory_session.reason == "advisory_session_not_acquired"
    assert snapshot.authority.valid is False
    assert snapshot.authority.reason == "ownership_row_not_present"
    assert snapshot.authority_state.state == RuntimeAuthorityState.INIT
