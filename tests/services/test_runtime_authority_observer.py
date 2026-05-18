from apps.api.app.services.runtime_scheduler.runtime_advisory_session_service import (
    acquire_runtime_advisory_session,
)
from apps.api.app.services.runtime_scheduler.runtime_authority_observer import (
    run_with_runtime_authority_observer,
)
from apps.api.app.services.runtime_scheduler.runtime_authority_state import (
    RuntimeAuthorityState,
)
from apps.api.app.services.runtime_scheduler import runtime_session_identity


class _FakeScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar(self):
        return self._value


class _FakeConnection:
    def __init__(self, *, acquire_result=True, fail_on_execute=False):
        self.acquire_result = acquire_result
        self.fail_on_execute = fail_on_execute

    def execute(self, statement, params=None):
        if self.fail_on_execute:
            raise RuntimeError("connection_failed")

        sql = str(statement)

        if "pg_try_advisory_lock" in sql:
            return _FakeScalarResult(self.acquire_result)

        if "pg_advisory_unlock" in sql:
            return _FakeScalarResult(True)

        return _FakeScalarResult(1)

    def close(self):
        pass


class _FakeEngine:
    def __init__(self, connection):
        self.connection = connection

    def connect(self):
        return self.connection


def setup_function():
    runtime_session_identity._runtime_session_identities.clear()
    runtime_session_identity._runtime_session_local_states.clear()


def test_authority_observer_runs_tick_even_when_authority_invalid():
    called = []

    observed = run_with_runtime_authority_observer(
        scheduler_name="auto_pick_internal",
        advisory_lock=None,
        ownership_row_present=False,
        local_identity_matches=False,
        local_runtime_generation=None,
        durable_runtime_generation=None,
        heartbeat_fresh=False,
        runtime_health_valid=False,
        fn=lambda: called.append("tick") or {"ok": True},
    )

    assert observed.result == {"ok": True}
    assert called == ["tick"]
    assert observed.authority_snapshot.authority.valid is False
    assert observed.authority_snapshot.authority_state.state == RuntimeAuthorityState.INIT


def test_authority_observer_reports_active_snapshot_without_blocking_tick():
    connection = _FakeConnection(acquire_result=True)
    acquired = acquire_runtime_advisory_session(
        engine=_FakeEngine(connection),
        scheduler_name="auto_pick_internal",
    )

    observed = run_with_runtime_authority_observer(
        scheduler_name="auto_pick_internal",
        advisory_lock=acquired.lock,
        ownership_row_present=True,
        local_identity_matches=True,
        local_runtime_generation=3,
        durable_runtime_generation=3,
        heartbeat_fresh=True,
        runtime_health_valid=True,
        fn=lambda: "ran",
    )

    assert observed.result == "ran"
    assert observed.authority_snapshot.authority.valid is True
    assert observed.authority_snapshot.authority_state.state == RuntimeAuthorityState.ACTIVE


def test_authority_observer_preserves_tick_exception_after_snapshot():
    try:
        run_with_runtime_authority_observer(
            scheduler_name="auto_pick_internal",
            advisory_lock=None,
            ownership_row_present=False,
            local_identity_matches=False,
            local_runtime_generation=None,
            durable_runtime_generation=None,
            heartbeat_fresh=False,
            runtime_health_valid=False,
            fn=lambda: (_ for _ in ()).throw(RuntimeError("tick_failed")),
        )
    except RuntimeError as exc:
        assert str(exc) == "tick_failed"
    else:
        raise AssertionError("Expected tick_failed")
