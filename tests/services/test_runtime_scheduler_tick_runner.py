from apps.api.app.services.runtime_scheduler.tick_runner import (
    SchedulerTickRunner,
)


def test_tick_runner_executes_success_lifecycle():
    calls = []

    def success(**kwargs):
        calls.append(("success", kwargs))

    def failure(**kwargs):
        calls.append(("failure", kwargs))

    runner = SchedulerTickRunner(
        scheduler_name="AUTO_PICK",
        db=object(),
        on_success=success,
        on_failure=failure,
    )

    result = runner.run(lambda: {"ok": True})

    assert result == {"ok": True}
    assert calls[0][0] == "success"


def test_tick_runner_executes_failure_lifecycle():
    calls = []

    def success(**kwargs):
        calls.append(("success", kwargs))

    def failure(**kwargs):
        calls.append(("failure", kwargs))

    runner = SchedulerTickRunner(
        scheduler_name="AUTO_PICK",
        db=object(),
        on_success=success,
        on_failure=failure,
    )

    try:
        runner.run(lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    except RuntimeError:
        pass
    else:
        raise AssertionError("runner must re-raise exceptions")

    assert calls[0][0] == "failure"


def test_tick_runner_commits_after_success():
    class DB:
        committed = False

        def commit(self):
            self.committed = True

        def rollback(self):
            raise AssertionError("rollback should not run")

    db = DB()

    runner = SchedulerTickRunner(
        scheduler_name="AUTO_PICK",
        db=db,
        on_success=lambda **_: None,
        on_failure=lambda **_: None,
    )

    runner.run_with_db_transaction(lambda: {"ok": True})

    assert db.committed is True


def test_tick_runner_can_wrap_success_with_optional_observer():
    calls = []

    def success(**kwargs):
        calls.append(("success", kwargs))

    def failure(**kwargs):
        calls.append(("failure", kwargs))

    def observer(fn):
        calls.append(("observer_before", {}))
        result = fn()
        calls.append(("observer_after", {}))
        return result

    runner = SchedulerTickRunner(
        scheduler_name="AUTO_PICK",
        db=object(),
        on_success=success,
        on_failure=failure,
    )

    result = runner.run(lambda: {"ok": True}, observer=observer)

    assert result == {"ok": True}
    assert calls[0][0] == "observer_before"
    assert calls[1][0] == "observer_after"
    assert calls[2][0] == "success"


def test_tick_runner_observer_exception_uses_failure_lifecycle():
    calls = []

    def observer(fn):
        raise RuntimeError("observer_failed")

    runner = SchedulerTickRunner(
        scheduler_name="AUTO_PICK",
        db=object(),
        on_success=lambda **kwargs: calls.append(("success", kwargs)),
        on_failure=lambda **kwargs: calls.append(("failure", kwargs)),
    )

    try:
        runner.run(lambda: {"ok": True}, observer=observer)
    except RuntimeError as exc:
        assert str(exc) == "observer_failed"
    else:
        raise AssertionError("Expected observer_failed")

    assert calls[0][0] == "failure"
